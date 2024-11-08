# program to run in systemd


import time
import wave
import argparse
import numpy as np
from pathlib import Path

from .hw import HW

def parse_args():
    parser = argparse.ArgumentParser(prog="recorder",
        description="run recorder program for MUAS mic line array")

def recorder():

    hw = HW()
    hw.set_use_fake_mics(False)
    hw.set_store_raw_data(True)
    channels = 12
    button_hold_amount = 8
    IDLE = True
    RECORD = True
    file_index = 0
    chunk_num = 0
    basepath = '/home/nixos'

    # create directory for error logs
    Path(f'{basepath}/logs').mkdir(exist_ok=True)

    # Recorder Script
    print('Recorder Script is Running')
    while True:

        # IDLE STATE
        print('-' * 30)
        print('idle...')
        # Initiate LED Idle Sequence
        button_counter = 0
        while IDLE:
            hw.LED_idle()
            # Check Button State / Wait for Press
            if hw.get_button_state():
                hw.button_press_indicate(button_counter)
                button_counter += 1
                if button_counter == button_hold_amount:
                    hw.button_press_indicate(button_counter)
                    IDLE = False

            time.sleep(0.1)

        # ---------------------------------------------------
        # RECORD STATE
        print('-' * 30)
        print('recording setup initiated...')
        hw.LED_quick_blink()
        time.sleep(2)

        # Get gain value from switches
        print(f'---- Gain Value: {hw.get_gain()}')
        hw.set_gain(hw.get_gain())

        # ---------------------------------------------------
        # Filename Logic
        latest_num = -1
        for path in Path(basepath).rglob('*.wav'):
            prefix = int(path.stem.split('_')[0])
            latest_num = max(latest_num, prefix)
        if latest_num == -1:
            file_index = 0
        else:
            file_index = latest_num + 1

        filename = f'{basepath}/{file_index}_{chunk_num}.wav'
        print(f'---- File Name: {filename}')

        # ---------------------------------------------------
        # create wav file to save
        wav = wave.open(filename, "wb")
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(hw.mic_freq_hz)

        # ---------------------------------------------------
        # create a metadata file with info about recording





        # ---------------------------------------------------
        # Initial LED Recording Sequence
        hw.LED_on()
        # monitor file size
        filesize = 0
        # swap buffers at the beginning since the current one probably overflowed
        hw.swap_buffers()

        print('---- Data Capturing')
        button_counter = 0
        while RECORD:
            try:
                data = hw.get_data()

            # record any errors to an error log file
            except ValueError:
                print('---- oops, probably overflowed')
                continue

            print(f'---- Samples: {len(data)}')
            filesize += (len(data) * channels * 16) / (8 * 1000 * 1000) # Mega Bytes
            wav.writeframesraw(np.ascontiguousarray(data[:, :channels]))

            # Check Button State / Wait for Press
            if hw.get_button_state():
                hw.button_press_indicate(button_counter)
                button_counter += 1
                if button_counter == button_hold_amount:
                    hw.button_press_indicate(button_counter)
                    RECORD = False

            if filesize >= 4000:
                # create new recording with incremented chunk number
                print('---- File Size Limit Reached')
                pass

            time.sleep(0.1)

        # ---------------------------------------------------
        # End Recording
        wav.close()
        print('---- Recording Successful')
        # LED Flashing Action for Confirmation
        hw.LED_quick_blink()
        print(f'File Size: {filesize} MB')


        # ---------------------------------------------------
        # Reset all Flags to start loop over
        file_index += 1
        IDLE = True
        RECORD = True
        hw.LED_off()
        time.sleep(2)




if __name__ == "__main__":
    recorder()

