import scipy.io.wavfile as wav
import scipy.io as sio
import audiotools
import numpy
import math
import pydub
import random
from features import mfcc
from features import logfbank
import os
import sys

if len(sys.argv)!=5:
    print 'Usage: beta_script.py <pathtodir> <referenceFile> <noiseFile> <output_root_directory>'
    sys.exit()

pathtodir = sys.argv[1]
referenceFile = sys.argv[2]
noiseFile = sys.argv[3]
output_root_directory =sys.argv[4]


def audioeval(speechFile, referenceFile,noiseFile, root_dir_name, output_root_directory):
	"This function evaluates a single audio file."
	#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	# ReplayGain calculation of reference
	ref = audiotools.open(referenceFile)
	ref_replay_gain = audiotools.calculate_replay_gain([ref])
	ref_track_gain = list(list(ref_replay_gain)[0])[1]
	print ref_track_gain

	# ReplayGain calculation of example speech file
	speech = audiotools.open(speechFile)
	speech_replay_gain = audiotools.calculate_replay_gain([speech])
	speech_track_gain = list(list(speech_replay_gain)[0])[1]
	print speech_track_gain

	# Normalization of example speech file
	(rate_speech, data_speech) = wav.read(speechFile)
	gain = ref_track_gain-speech_track_gain
	data_normalized = numpy.asarray(data_speech*math.pow(10, (-(gain)/20)), dtype=numpy.int16)
	normalizedFile = "speech_normalized.wav"
	wav.write(normalizedFile , rate_speech, data_normalized)

	# Loudness test of normalized example speech
	test = audiotools.open(normalizedFile)
	test_replay_gain = audiotools.calculate_replay_gain([test])
	test_track_gain = list(list(test_replay_gain)[0])[1]
	print test_track_gain

	# Randomly choosing one noise file from the pool
	# here I just fix one waiting for implementation later

	# Using pydub API to calculate the length of normalized speech file and the noise file
	speech_normalized = pydub.AudioSegment.from_wav(normalizedFile)
	# !there is a bug of this function: can NOT open some noise files
	noise = pydub.AudioSegment.from_wav(noiseFile)
	speech_normalized_length = speech_normalized.duration_seconds
	noise_length = noise.duration_seconds

	# Selecting a randow start point of the noise file to get a segment of the required length
	start = random.randrange(0,int(noise_length-speech_normalized_length)*1000)
	# pydub does things in milliseconds
	noise_segmented = noise[start:int(start+speech_normalized_length*1000)]
	noise_segmented.export("noise_segmented.wav",format="wav")

	# Linear fading of sharply segmented noised segment
	# 1 sec fade in, 1 sec fade out
	noise_faded = noise_segmented.fade_in(1000).fade_out(1000)
	noise_faded.export("noise_faded.wav",format="wav")

	# how long is good? 1 sec?

	# Picking a random signal to noise ratio (SNR)
	SNR_ratio = random.randint(-2, 20)
	print "SNR_ratio: " + str(SNR_ratio)

	# loudness in dBFS (Decibels relative to full scale)
	# (all peak measurements will be negative numbers)
	speech_dB = speech_normalized.dBFS
	noise_dB = noise_segmented.dBFS
	print "loudness of speech: " + str(speech_dB)
	print "loudness of noise: " + str(noise_dB)

	# Change the amplitude (generally, loudness) of the speech by SNR ratio from noise. 
	# Gain is specified in dB. 
	gain = SNR_ratio-(speech_dB-noise_dB)
	print "gain: " + str(gain)
	speech_SNRed = speech_normalized.apply_gain(gain)
	print "loudness of adjusted speech: " + str(speech_SNRed.dBFS)
	# check SNR
	print "check SNR: " + str(speech_SNRed.dBFS - noise_dB)

	# mix the two tracks by adding the respective samples
	# (If the overlaid AudioSegment is longer than this one, the result will be truncated)
	noisy_speech = speech_SNRed.overlay(noise_segmented)
	noisy_speech.export("noisy_speech.wav",format="wav")
	# Since the sample values have increased through the summation, it is possible that they exceed the maximum imposed by the data type. How this API deals with this problem?


	# draw an impulse response from the pool
	# ...waiting to implement

	# peak-normalize it to 0dB (=1) by dividing the IR vector through its maximum value.
	(rate_IR, data_IR) = wav.read("htc_desk.wav")
	# data_IR.dtype is int16, change it into float64
	data_IR = data_IR.astype(numpy.float64) 
	data_IR = data_IR / data_IR.max()

	# convolve speech with the normalized IR
	(rate_noisy_speech, data_noisy_speech) = wav.read("noisy_speech.wav")
	speech_convolved = numpy.convolve(data_IR, data_noisy_speech)

	#print "Root Directory Name: "+str(root_dir_name)
	output_directory = os.path.join(output_root_directory, root_dir_name,'convoluted') 
	#print output_directory

	if not os.path.exists(output_directory):
    		os.makedirs(output_directory)

	#speech_convolved_file = output_directory+'/'+str(os.path.splitext(speechFile)[0])+"_convolved.wav"
	speech_convolved_file_name = os.path.basename(speechFile)
	#print "Speech File Name: "+str(speech_convolved_file_name)	
	speech_convolved_file = os.path.join(output_directory, speech_convolved_file_name)
	print "Final output file path: "+str(speech_convolved_file)	
	
	# cut the convolved track to its original length if prolonged and store the resulting track
	wav.write(speech_convolved_file, rate_noisy_speech, speech_convolved[:data_noisy_speech.size])

	# MFCC Feature extraction
	# Do the default parameters (frame size etc.) work for you?
	(rate,sig) = wav.read(speech_convolved_file)
	mfcc_feat = mfcc(sig,rate)
	print "MFCC Shape:"
	print mfcc_feat.shape
	print mfcc_feat
	#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	## Cleaup code which deletes the intermediate files which get generated.
	return;



# traverse root directory, and list directories as dirs and files as files
for root, dirs, files in os.walk(pathtodir):
    path = root.split('/')
    #print (len(path) - 1) *'---' , os.path.basename(root)       
    for file in files:
        if (file.lower().endswith('.wav')):
           print 'Current File: ', file
           speechFilePath = root+str(file) 
           tmp = os.path.dirname(speechFilePath)
           #print "Root: "+str(os.path.basename(tmp))
           #print os.path.basename(speechFilePath)
           root_dir_name = os.path.basename(tmp)
           #print "Main Root Directory Name: "+str(os.path.basename(root))
           audioeval(speechFilePath,referenceFile,noiseFile,root_dir_name,output_root_directory)
print "Operations Finished!"

