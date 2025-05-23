import pathlib

from amaranth import *
from amaranth.lib.wiring import Component, In, Out, connect, flipped
from amaranth.lib.cdc import FFSynchronizer

from amaranth_soc import csr
from amaranth_soc.csr import Field

import numpy as np

from .hps_bus import AudioRAMBus
from .audio_constants import MIC_FREQ_HZ, NUM_TAPS, NUM_MICS, NUM_CHANS
from .audio_mic import MicCapture, MicCaptureRegs
from .audio_convolve import Convolver
from .audio_stream import SampleStreamFIFO, SampleWriter


class SystemRegs(Component):
    csr_bus: In(csr.Signature(addr_width=2, data_width=32))
    switches_raw: In(4)
    button_raw: In(1)
    button_off_raw: In(1)
    leds: Out(8)

    store_raw_data: Out(1)

    class SysParams1(csr.Register, access="r"):
        num_mics: Field(csr.action.R, 8)
        num_chans: Field(csr.action.R, 8)
        num_taps: Field(csr.action.R, 8)

    class SysParams2(csr.Register, access="r"):
        mic_freq_hz: Field(csr.action.R, 16)

    class RawDataCtrl(csr.Register, access="rw"):
        # 1 to store raw mic data, 0 to store convolved data. the switch is
        # nowhere near clean
        store_raw_data: Field(csr.action.RW, 1)

    class ButtonSwitch(csr.Register, access="rw"):
        button_state: Field(csr.action.R, 1)
        switches_state: Field(csr.action.R, 4)
        leds: Field(csr.action.RW, 8)
        button_off_state: Field(csr.action.R, 1)

    def __init__(self):
        self._sys_params_1 = self.SysParams1()
        self._sys_params_2 = self.SysParams2()
        self._raw_data_ctrl = self.RawDataCtrl()
        self._button_switch = self.ButtonSwitch()

        csr_sig = self.__annotations__["csr_bus"].signature
        builder = csr.Builder(
            addr_width=csr_sig.addr_width, data_width=csr_sig.data_width)
        builder.add("sys_params_1", self._sys_params_1)
        builder.add("sys_params_2", self._sys_params_2)
        builder.add("raw_data_ctrl", self._raw_data_ctrl)
        builder.add("button_switch", self._button_switch)

        self._csr_bridge = csr.Bridge(builder.as_memory_map())

        super().__init__() # initialize component and attributes from signature

        self.csr_bus.memory_map = self._csr_bridge.bus.memory_map

    def elaborate(self, platform):
        m = Module()

        # bridge containing CSRs
        m.submodules.csr_bridge = csr_bridge = self._csr_bridge
        connect(m, flipped(self.csr_bus), csr_bridge.bus)

        # initialize read-only parameter fields
        m.d.comb += [
            self._sys_params_1.f.num_mics.r_data.eq(NUM_MICS),
            self._sys_params_1.f.num_chans.r_data.eq(NUM_CHANS),
            self._sys_params_1.f.num_taps.r_data.eq(NUM_TAPS),
            self._sys_params_2.f.mic_freq_hz.r_data.eq(MIC_FREQ_HZ),
        ]

        m.submodules += FFSynchronizer(self.switches_raw, self._button_switch.f.switches_state.r_data)
        m.submodules += FFSynchronizer(self.button_raw, self._button_switch.f.button_state.r_data)
        m.submodules += FFSynchronizer(self.button_off_raw, self._button_switch.f.button_off_state.r_data)


        # forward register values
        m.d.sync += [
            self.store_raw_data.eq(self._raw_data_ctrl.f.store_raw_data.data),
            self.leds.eq(self._button_switch.f.leds.data),
        ]

        return m

class Top(Component):
    button_raw: In(1)
    switches_raw: In(4)
    status_leds: Out(8)
    button_off_raw: In(1)

    audio_ram: Out(AudioRAMBus())
    csr_bus: In(csr.Signature(addr_width=8, data_width=32))

    mic_sck: Out(1) # microphone data bus
    mic_ws: Out(1)
    mic_data_raw: In(NUM_MICS//2)

    def __init__(self):
        csr_sig = self.__annotations__["csr_bus"].signature
        self._csr_decoder = csr.Decoder(
            addr_width=csr_sig.addr_width, data_width=csr_sig.data_width)

        self._sample_writer = SampleWriter()
        self._mic_capture_regs = MicCaptureRegs(o_domain="mic_capture")
        self._system_regs = SystemRegs()

        # add subordinate buses to decoder
        # fix addresses for now for program consistency
        self._csr_decoder.add(self._sample_writer.csr_bus, addr=0)
        self._csr_decoder.add(self._mic_capture_regs.csr_bus, addr=4)
        self._csr_decoder.add(self._system_regs.csr_bus, addr=8)

        super().__init__() # initialize component and attributes from signature

        self.csr_bus.memory_map = self._csr_decoder.bus.memory_map

    def elaborate(self, platform):
        m = Module()


        # decode busses for all the subordinate components
        m.submodules.csr_decoder = self._csr_decoder
        connect(m, flipped(self.csr_bus), self._csr_decoder.bus)

        # hook up system registers
        m.submodules.system_regs = system_regs = self._system_regs
        m.d.comb += [
            system_regs.switches_raw.eq(self.switches_raw),
            system_regs.button_raw.eq(self.button_raw),
            system_regs.button_off_raw.eq(self.button_off_raw),
            self.status_leds.eq(system_regs.leds)
        ]

        # instantiate mic capture unit in its domain
        m.submodules.mic_capture = mic_capture = \
            DomainRenamer("mic_capture")(MicCapture())
        m.d.comb += [
            self.mic_sck.eq(mic_capture.mic_sck),
            self.mic_ws.eq(mic_capture.mic_ws),
            mic_capture.mic_data_raw.eq(self.mic_data_raw),
        ]

        # instantiate and hook up mic capture registers
        m.submodules.mic_capture_regs = cap_regs = self._mic_capture_regs
        m.d.comb += [
            mic_capture.gain.eq(cap_regs.gain),
            mic_capture.use_fake_mics.eq(cap_regs.use_fake_mics)
        ]

        # FIFO to cross domains from mic capture
        m.submodules.mic_fifo = mic_fifo = \
            SampleStreamFIFO(w_domain="mic_capture")
        connect(m, mic_capture.samples, mic_fifo.samples_w)

        # load prepared coefficient data
        coeff_path = pathlib.Path(__file__).parent/"coefficients.txt"
        coefficients = np.loadtxt(coeff_path, dtype=np.float64)
        coefficients = coefficients.reshape(NUM_CHANS, NUM_TAPS, NUM_MICS)
        coefficients /= NUM_MICS # legacy; we should change the generator

        # FIFO to cross domains to the convolver
        m.submodules.conv_i_fifo = conv_i_fifo = \
            SampleStreamFIFO(w_domain="sync", r_domain="convolver")

        # instantiate convolver in its domain
        m.submodules.convolver = convolver = \
            DomainRenamer("convolver")(Convolver(coefficients))
        connect(m, conv_i_fifo.samples_r, convolver.samples_i)
        m.d.comb += convolver.samples_i_count.eq(conv_i_fifo.samples_count)

        # FIFO to cross domains from convolver to the writer
        m.submodules.conv_o_fifo = conv_o_fifo = \
            SampleStreamFIFO(w_domain="convolver")
        connect(m, convolver.samples_o, conv_o_fifo.samples_w)

        # writer to save sample data to memory
        m.submodules.sample_writer = sample_writer = self._sample_writer
        connect(m, sample_writer.audio_ram, flipped(self.audio_ram))

        # switch between saving raw sample data and convolved data
        with m.If(system_regs.store_raw_data):
            # connect mic fifo directly to sample writer
            connect(m, mic_fifo.samples_r, sample_writer.samples)
            m.d.comb += sample_writer.samples_count.eq(mic_fifo.samples_count)
        with m.Else():
            # run mic data through convolver
            connect(m, mic_fifo.samples_r, conv_i_fifo.samples_w)
            connect(m, conv_o_fifo.samples_r, sample_writer.samples)
            m.d.comb += sample_writer.samples_count.eq(
                conv_o_fifo.samples_count)

        return m
