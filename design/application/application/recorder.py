# program to run in systemd


import time
import wave
import argparse

import numpy as np

from .hw import HW

def parse_args():
    parser = argparse.ArgumentParser(prog="recorder",
        description="run recorder program for MUAS mic line array")

# def recorder():
#
#     hw = HW()
#     hw.set_use_fake_mics(False)
#     hw.set_store_raw_data(True)
#     channels = 12
#
#     while True:
#
#         # Initiate LED Idle Sequence
#
#
#
#         # Check Button State and Wait for Press
#
#
#         # Get gain value from switches
#         gain = 1
#         hw.set_gain(gain)
#
#
#         # Filename Logic
#         # chunk_num = 0
#         # if file is none: filename = 0_0.wav
#         # else: filename = f'{int(file.name.split()[0]) + 1}_{chunk_num}.wav'
#
#
#         filename = ''
#         wav = wave.open(filename, "wb")
#         wav.setnchannels(channels)
#         wav.setsampwidth(2)
#         wav.setframerate(hw.mic_freq_hz)
#
#         # create a metadata file with info about recording
#
#
#         # monitor file size
#         filesize = 0
#
#
#         # swap buffers at the beginning since the current one probably overflowed
#         hw.swap_buffers()
#
#         print("capture is starting!")
#         while True:
#             try:
#                 data = hw.get_data()
#
#             # record any errors to an error log file
#             except ValueError:
#                 print("oops, probably overflowed")
#                 continue
#
#             print(f"got {len(data)} samples")
#             wav.writeframesraw(np.ascontiguousarray(data[:, :channels]))
#
#             # Initial LED Recording Sequence
#
#             time.sleep(0.1)
#
#
#         # End Recording
#
#         wav.close()
#
#
#         # LED Flashing Action for Confirmation
#
#         # Start the Loop Over


def recorder():
    print('Recorder Should be Running!')
    print('YAY!!!')


if __name__ == "__main__":
    recorder()

