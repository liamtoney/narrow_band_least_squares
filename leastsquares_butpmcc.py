############################################################################
################## Narrow Band Least Squares Method ########################
############################################################################
### Breaks up frequencies into multiple bands (similar to PMCC method) 
### Normal least squares uses the entire frequency  band for calculation 
### Authors: Sneha Bhetanabhotla, Alex Iezzi, and Robin Matoza 
### University of California Santa Barbara 
### Contact: Alex Iezzi (amiezzi@ucsb.edu) 
### Last Modified: September 28, 2021 
############################################################################

###############
### Imports ###
###############
from waveform_collection import gather_waveforms 
from obspy.core import UTCDateTime, Stream, read
import numpy as np
import math as math
from helpers import get_freqlist, get_winlenlist, filter_data, make_float
from plotting import broad_filter_response_plot, processing_parameters_plot, pmcc_like_plot
from array_processing.algorithms.helpers import getrij
from array_processing.tools.plotting import array_plot
from lts_array import ltsva
from scipy import signal 
import multiprocessing


##############################################################################
##################
### User Input ###
##################

### Data information ###
# Data collection
SOURCE = 'IRIS'                                     # Data source; 'IRIS' or 'local'


# IRIS Example
NETWORK = 'IM'
STATION = 'I53H?'
LOCATION = '*'
CHANNEL = 'BDF'
START = UTCDateTime('2018-12-19T01:45:00')
END = START + 20*60



'''

# Bogoslof IRIS Example
NETWORK = 'AV'
STATION = 'DLL*'
LOCATION = '*'
CHANNEL = 'HD*'
START = UTCDateTime('2017-01-02T23:00:00')
END = START + 60*60
'''

'''
# Local Example
START = UTCDateTime('2010-05-28T13:30:00')          # start time for processing (UTCDateTime)
END = UTCDateTime('2010-05-28T18:30:00')            # end time for processing (UTCDateTime)
FMT = '%Y-%m-%dT%H:%M:%S.%f'                        # date/time format 

# RIOE 
latlist = [-1.74812, -1.74749, -1.74906, -1.74805]
lonlist = [-78.62735, -78.62708, -78.62742, -78.62820]
calib = -0.000113  # Pa/count

data_dir = '/Users/aiezzi/Desktop/NSF_Postdoc/Array_Processing_Research/PMCC_Training/data/'       # directory where data is located

'''

### Filtering ###
FMIN = 0.07                  # [Hz]
FMAX = 5.                   # [Hz] #should not exceed Nyquist
nbands = 10                # number of frequency bands 
freq_band_type = 'log'   # indicates linear or logarithmic spacing for frequency bands; 'linear' or 'log'
filter_type = 'cheby1'      # filter type; 'butter', 'cheby1'
filter_order = 2
filter_ripple = 0.01


### Window Length ###
WINOVER = 0.5               # window overlap
window_length = 'adaptive'  # 'constant' or 'adaptive'
WINLEN = 50                 # window length [s]; used if window_length = 'constant' AND if window_length = 'adaptive' (because of broadband processing)
WINLEN_1 = 60              # window length for band 1 (lowest frequency) [s]; only used if window_length = 'adaptive'
WINLEN_X = 30               # window length for band X (highest frequency) [s]; only used if window_length = 'adaptive'

### Array processing ###
ALPHA = 1.0                 # Use ordinary least squares processing (not trimmed least squares)
mdccm_thresh = 0.6          # Threshold value of MdCCM for plotting; Must be between 0 and 1

### Figure Save Options ###
save_dir = '/Users/aiezzi/Desktop/NSF_Postdoc/Array_Processing_Research/narrow_band_least_squares/Figures/'         # directory in which to save figures
file_type = '.png'                          # file save type
dpi_num = 300                               # dots per inch for plot save




##############################################################################
######################
### End User Input ###
######################
##############################################################################


##############################################################################
###################
### Gather Data ###
###################
if SOURCE == 'IRIS':
    st = gather_waveforms(SOURCE, NETWORK, STATION, LOCATION, CHANNEL, START, END, remove_response=True)
    latlist = [tr.stats.latitude for tr in st]
    lonlist = [tr.stats.longitude for tr in st]
elif SOURCE == 'local':
    # Read in waveforms 
    st = Stream()
    st += read(data_dir + '*.mseed')
    st.trim(START, END)
    # Calibrate the data 
    for ii in range (len(st)):
        tr = st[ii]
        tr.data = tr.data*calib



##################################################################################
#####################################
### Set Up Narrow Frequency Bands ###
#####################################										
freqlist = get_freqlist(FMIN, FMAX, freq_band_type, nbands)


##################################################################################
#############################
### Set Up Window Lengths ###
############################# 
WINLEN_list = get_winlenlist(window_length, nbands, WINLEN, WINLEN_1, WINLEN_X)


##################################################################################
######################
### Array Geometry ###
######################
# Convert array coordinates to array processing geometry
rij = getrij(latlist, lonlist)


##################################################################################
##################################
### Broadband Array Processing ###
##################################

stf_broad, Fs, sos = filter_data(st, filter_type, FMIN, FMAX, filter_order, filter_ripple)
vel, baz, t, mdccm, stdict, sig_tau = ltsva(stf_broad, rij, WINLEN, WINOVER, ALPHA)

# Plot broadband array processing results
fig1, axs1 = array_plot(stf_broad, t, mdccm, vel, baz, ccmplot=True, mcthresh=mdccm_thresh, sigma_tau=sig_tau)
fig1.savefig(save_dir + 'LeastSquares', dpi=dpi_num)
plt.close(fig1)


###############################################
### Broadband filter frequency reponse Plot ###
###############################################
FMINL = math.log(0.01, 10)
FMAXL = math.log(Fs/2, 10)
freq_resp_list = np.logspace(FMINL, FMAXL, num = 1000)
w_broad, h_broad = signal.sosfreqz(sos,freq_resp_list,fs=Fs)


fig = broad_filter_response_plot(w_broad, h_broad, FMIN, FMAX, filter_type, filter_order, filter_ripple)
#plt.tight_layout()
fig.savefig(save_dir + 'Filter_Frequency_Response_Broadband', dpi=dpi_num)
plt.close(fig)



##################################################################################
###############################
### Initialize Numpy Arrays ###
###############################
if window_length == 'constant':
    sampinc = int((1-WINOVER)*WINLEN)
elif window_length == 'adaptive':
    sampinc = int((1-WINOVER)*WINLEN_X)
npts = len(st[0].data)
its = np.arange(0,npts,sampinc)
nits = len(its)-1
vector_len = int(nits/Fs)

# Initialize arrays to be as large as the number of windows for the highest frequency band
vel_array = np.empty((nbands,vector_len))
baz_array = np.empty((nbands,vector_len))
mdccm_array = np.empty((nbands,vector_len))
t_array = np.empty((nbands,vector_len))

# Initialize Frequency response arrays
w_array = np.empty((nbands,len(w_broad)), dtype = 'complex_')
h_array = np.empty((nbands,len(h_broad)), dtype = 'complex_')


# Parallel Processing
num_cores = multiprocessing.cpu_count()
print(num_cores)


########################################
### Run Narrow Band Array Processing ###
########################################
num_compute_list = []
for ii in range(nbands): 
    tempfmin = freqlist[ii]
    tempfmax = freqlist[ii+1]

    tempst_filter, Fs, sos = filter_data(st, filter_type, tempfmin, tempfmax, filter_order, filter_ripple)
    w, h = signal.sosfreqz(sos,freq_resp_list,fs=Fs)
    w_array[ii,:] = w
    h_array[ii,:] = h


    # Run Array Processing 
    vel, baz, t, mdccm, stdict, sig_tau = ltsva(tempst_filter, rij, WINLEN_list[ii], WINOVER, ALPHA)

    # Convert array processing output to numpy array of floats
    vel_float = make_float(vel)
    baz_float = make_float(baz)
    mdccm_float = make_float(mdccm)
    t_float = make_float(t)


    ####################################
    ### Save Array Processing Output ###
    ####################################
    vel_array[ii,:len(vel_float)] = vel_float
    baz_array[ii,:len(baz_float)] = baz_float
    mdccm_array[ii,:len(mdccm_float)] = mdccm_float
    t_array[ii,:len(t_float)] = t_float
    num_compute_list.append(len(vel_float))





##################################################################################
###################################
### Plot: Processing Parameters ###
###################################
fig = processing_parameters_plot(rij, freqlist, WINLEN_list, nbands, FMIN, FMAX, w_array, h_array, filter_type, filter_order, filter_ripple)
fig.savefig(save_dir + 'Processing_Parameters', dpi=dpi_num)
plt.close(fig)



##################################################################################
#######################
### Plot: PMCC-like ###
#######################
fig = pmcc_like_plot(FMIN, FMAX, stf_broad, nbands, freqlist, vel_array, baz_array, mdccm_array, t_array, num_compute_list, mdccm_thresh)
fig.savefig(save_dir + 'LeastSquaresButPMCC', dpi=dpi_num)
plt.close(fig)





#height of rectangles goes from tempfmin and tempfmax, width is from tlist[x] to tlist[x+1]
#each frequency band graph has subplots of baz, v, mdccm, sig tau
#plotting goes inside for loop
#see bulletin_updated for colorbar: backaz from 0 - 360, trace v from 0.25 - 0.45 km/s, goes outside for loop

#%% Array processing and plotting using least squares

#%% Array processing. ALPHA = 1.0: least squares processing.

#hard coded scatter plots for all the lists
""" fig1, axs1 = array_plot(filteredst[0], tlist[0], mdccmlist[0], vellist[0], bazlist[0], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[0])
fig2, axs2 = array_plot(filteredst[1], tlist[1], mdccmlist[1], vellist[1], bazlist[1], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[1])
fig3, axs3 = array_plot(filteredst[2], tlist[2], mdccmlist[2], vellist[2], bazlist[2], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[2])
fig4, axs4 = array_plot(filteredst[3], tlist[3], mdccmlist[3], vellist[3], bazlist[3], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[3])
fig5, axs5 = array_plot(filteredst[4], tlist[4], mdccmlist[4], vellist[4], bazlist[4], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[4])
fig6, axs6 = array_plot(filteredst[5], tlist[5], mdccmlist[5], vellist[5], bazlist[5], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[5])
fig7, axs7 = array_plot(filteredst[6], tlist[6], mdccmlist[6], vellist[6], bazlist[6], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[6])
fig8, axs8 = array_plot(filteredst[7], tlist[7], mdccmlist[7], vellist[7], bazlist[7], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[7])
fig9, axs9 = array_plot(filteredst[8], tlist[8], mdccmlist[8], vellist[8], bazlist[8], ccmplot=True, mcthresh=0.6, sigma_tau=sig_taulist[8])


if freq_band_type == 'linear':
    fig1.savefig(save_dir + 'MCCM_example_least_squares_linear_1.png', dpi=150)
    fig2.savefig(save_dir + 'MCCM_example_least_squares_linear_2.png', dpi=150)
    fig3.savefig(save_dir + 'MCCM_example_least_squares_linear_3.png', dpi=150)
    fig4.savefig(save_dir + 'MCCM_example_least_squares_linear_4.png', dpi=150)
    fig5.savefig(save_dir + 'MCCM_example_least_squares_linear_5.png', dpi=150)
    fig6.savefig(save_dir + 'MCCM_example_least_squares_linear_6.png', dpi=150)
    fig7.savefig(save_dir + 'MCCM_example_least_squares_linear_7.png', dpi=150)
    fig8.savefig(save_dir + 'MCCM_example_least_squares_linear_8.png', dpi=150)
    fig9.savefig(save_dir + 'MCCM_example_least_squares_linear_9.png', dpi=150)
elif freq_band_type == 'log':
    fig1.savefig(save_dir + 'MCCM_example_least_squares_log_1.png', dpi=150)
    fig2.savefig(save_dir + 'MCCM_example_least_squares_log_2.png', dpi=150)
    fig3.savefig(save_dir + 'MCCM_example_least_squares_log_3.png', dpi=150)
    fig4.savefig(save_dir + 'MCCM_example_least_squares_log_4.png', dpi=150)
    fig5.savefig(save_dir + 'MCCM_example_least_squares_log_5.png', dpi=150)
    fig6.savefig(save_dir + 'MCCM_example_least_squares_log_6.png', dpi=150)
    fig7.savefig(save_dir + 'MCCM_example_least_squares_log_7.png', dpi=150)
    fig8.savefig(save_dir + 'MCCM_example_least_squares_log_8.png', dpi=150)
    fig9.savefig(save_dir + 'MCCM_example_least_squares_log_9.png', dpi=150) """





# %%
