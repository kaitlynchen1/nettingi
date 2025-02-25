#supporting functions for data reduction
#before and/or after mitigation


import numpy as np
from scipy import signal
from scipy import stats
from scipy.integrate import cumtrapz


import os
import pickle
from blimpy.guppi import GuppiRaw


import glob


def load_srdps():
    pass







def pfb_mask(x, nchan, ntap, window="hann", fs=1.0, return_freqs=False, 
        force_complex=False):
    """
    Channelize data using a polyphase filterbank

    Parameters
    ----------
    x : ndarray
       The input time series.
    nchan : int
       The number of channels to form.
    ntap : int
       The number of PFB taps to use.
    window : str
       The windowing function to use for the PFB coefficients.
    fs : float
       The sampling frequency of the input data.
    return_freqs : bool
       If True, return the center frequency of each channel.
    force_complex : bool
       If True, treat input as complex even if the imaginary component is zero.

    Returns
    -------
    x_pfb : ndarray
       The channelized data
    freqs : ndarray
       The center frequency of each channel.  Omitted if 
       return_freqs == False
    
    Notes
    -----
    If the input data are real-valued then only positive frequencies
    are returned.
    """
    real = np.isreal(x).all() and not force_complex
    h = signal.firwin(ntap*nchan,cutoff=1.0/nchan,window="rectangular")
    h *= signal.get_window(window,ntap*nchan)
    nwin = x.shape[0]//ntap//nchan
    x = x[:nwin*ntap*nchan].reshape((nwin*ntap,nchan)).T
    #xma = np.ma.getmask(x)
    h = h.reshape((ntap,nchan)).T
    xs = np.ma.masked_array(np.zeros((nchan,ntap*(nwin-1)+1),dtype=x.dtype))
    for ii in range(ntap*(nwin-1)+1):
        xw = np.ma.masked_array(h*x[:,ii:ii+ntap],np.ma.getmask(x[:,ii:ii+ntap]))
        if np.ma.count_masked(xw) == 0:
            xs[:,ii] = xw.sum(axis=1)
        else:
            xs[:,ii] = np.empty(xw.shape[0],dtype=x.dtype)
            xs[:,ii] = np.nan
    xs = xs.T
    #compare input flagging vs. output flags
    #print(100.*(np.ma.count_masked(x)/x.size) , 100.*np.sum(np.isnan(xs))/xs.size)
    xpfb = np.fft.rfft(xs,nchan,axis=1) if real else np.fft.fft(xs,nchan,axis=1)
    xpfb *= np.sqrt(nchan)

    #print(100.*np.sum(np.isnan(xs))/xs.size, 100.*np.sum(np.isnan(xpfb))/xpfb.size)

    if return_freqs:
        freqs = np.fft.rfftfreq(nchan,d=1.0/fs) if real else \
                np.fft.fftfreq(nchan,d=1.0/fs)
        return xpfb,freqs
    else:
        return xpfb


def pfb(x, nchan, ntap, window="hann", fs=1.0, return_freqs=False, 
        force_complex=False):
    """
    Channelize data using a polyphase filterbank

    Parameters
    ----------
    x : ndarray
       The input time series.
    nchan : int
       The number of channels to form.
    ntap : int
       The number of PFB taps to use.
    window : str
       The windowing function to use for the PFB coefficients.
    fs : float
       The sampling frequency of the input data.
    return_freqs : bool
       If True, return the center frequency of each channel.
    force_complex : bool
       If True, treat input as complex even if the imaginary component is zero.

    Returns
    -------
    x_pfb : ndarray
       The channelized data
    freqs : ndarray
       The center frequency of each channel.  Omitted if 
       return_freqs == False
    
    Notes
    -----
    If the input data are real-valued then only positive frequencies
    are returned.
    """
    real = np.isreal(x).all() and not force_complex
    h = signal.firwin(ntap*nchan,cutoff=1.0/nchan,window="rectangular")
    h *= signal.get_window(window,ntap*nchan)
    nwin = x.shape[0]//ntap//nchan
    x = x[:nwin*ntap*nchan].reshape((nwin*ntap,nchan)).T
    h = h.reshape((ntap,nchan)).T
    xs = np.zeros((nchan,ntap*(nwin-1)+1),dtype=x.dtype)
    for ii in range(ntap*(nwin-1)+1):
        xw = h*x[:,ii:ii+ntap]
        xs[:,ii] = xw.sum(axis=1)
    xs = xs.T
    xpfb = np.fft.rfft(xs,nchan,axis=1) if real else np.fft.fft(xs,nchan,axis=1)
    xpfb *= np.sqrt(nchan)

    if return_freqs:
        freqs = np.fft.rfftfreq(nchan,d=1.0/fs) if real else \
                np.fft.fftfreq(nchan,d=1.0/fs)
        return xpfb,freqs
    else:
        return xpfb





#fine channelize the data, when no nans have been injected

def raw2spec(resolution,gr,infile):
    basenm = os.path.basename(infile)
    print(basenm)
    outfile_test = os.path.join('/data/scratch/IQRMresults',basenm.replace(".raw",f".{resolution}.spec.pkl"))
    print("hi")
   
    print(outfile_test)
    print("hi2")
    hdr0 = gr.read_first_header()
    fctr = float(hdr0["OBSFREQ"])
    bw = float(hdr0["OBSBW"])
    nchan = int(hdr0["OBSNCHAN"])
    chanbw = bw/nchan
    chanfreqs = fctr - 0.5*bw + chanbw*(np.arange(nchan)+0.5)
    nchan_pfb = 2**int(np.round(np.log2(np.abs(chanbw/(resolution/1e3)))))
    print(f'given output res is {resolution} kHz, actual will be {np.abs(chanbw/nchan_pfb)*1e3} khz')

    spectrum = np.zeros(nchan_pfb*nchan)

    gr.reset_index()
    for bb in range(gr.n_blocks):
        print("Working on block {0} of {1}".format(bb+1,gr.n_blocks))
        hdr,data = gr.read_next_data_block()
        x = data[:,:,0]
        y = data[:,:,1]
        for nn in range(data.shape[0]):
            xpfb = np.fft.fftshift(
                pfb(x[nn],nchan_pfb,12,force_complex=True),axes=-1)
            ypfb = np.fft.fftshift(
                pfb(y[nn],nchan_pfb,12,force_complex=True),axes=-1)
            spec = (np.mean(np.abs(xpfb)**2,axis=0)\
                    +np.mean(np.abs(ypfb)**2,axis=0))/2
            spectrum[nn*nchan_pfb:(nn+1)*nchan_pfb] += np.flip(spec[::-1])
    spectrum /= gr.n_blocks
    pfb_chanbw = chanbw/nchan_pfb
    freqs = chanfreqs[0]-0.5*pfb_chanbw+np.arange(nchan_pfb*nchan)*pfb_chanbw
    #bad_chans = np.arange(nchan)*nchan_pfb + nchan_pfb//2
    #mask = np.zeros(spectrum.shape)
    #mask[bad_chans] = 1
    #masked_spectrum = np.ma.masked_array(spectrum,mask)
    out1 = (freqs,spectrum)
#     #out2 = (freqs,masked_spectrum)
#     basenm = os.path.basename(infile)
    
    with open(os.path.join('/data/scratch/IQRMresults',basenm.replace(".raw",f".{resolution}.spec.pkl")),"wb") as f: 
        pickle.dump(out1,f)
        print(f)
    #with open(os.path.join(args.outdir,basenm.replace(".raw",".20.spec_mask.pkl")), "wb") as f: 
        #pickle.dump(out2,f)


#do fine channelization using a mask
def raw2spec_mask(resolution,gr,mask, infile, outfile):
    basenm = os.path.basename(infile)
    outfile_test = os.path.join('/data/scratch/IQRMresults',basenm.replace(".raw",f".{resolution}.spec.pkl"))
    print("hi")
   
    print(outfile_test)
    print("hi2")
    hdr0 = gr.read_first_header()
    fctr = float(hdr0["OBSFREQ"])
    bw = float(hdr0["OBSBW"])
    nchan = int(hdr0["OBSNCHAN"])
    chanbw = bw/nchan
    chanfreqs = fctr - 0.5*bw + chanbw*(np.arange(nchan)+0.5)
    nchan_pfb = 2**int(np.round(np.log2(np.abs(chanbw/(args.resolution/1e3)))))

    print(f'given output res is {resolution} kHz, actual will be {np.abs(chanbw/nchan_pfb)*1e3} khz')

    SKf = np.load(args.flags)
    SKM = int(args.SKM)

    spectrum = np.zeros(nchan_pfb*nchan)
    unflagged_blocks = np.zeros(nchan_pfb*nchan)

    gr.reset_index()
    for bb in range(gr.n_blocks):
        print(f"Working on block {bb+1} of {gr.n_blocks}")
        hdr,data = gr.read_next_data_block()
        x = data[:,:,0]
        y = data[:,:,1]

        #apply mask
        #find M
        M = int((x.shape[1]*gr.n_blocks) / SKf.shape[1])
        #pulse = np.ones((1,M,1))
        num_fbins = SKf.shape[1]//gr.n_blocks

        mask = SKf[:,bb*num_fbins:(bb+1)*num_fbins,:]

        #mask = np.kron(this_f,pulse)

        union_mask = np.copy(mask[:,:,0])
        union_mask[mask[:,:,1]==1] = 1

        #xma = np.ma.masked_array(x,union_mask)
        #yma = np.ma.masked_array(y,union_mask)

        for nn in range(data.shape[0]):
            #print('----',nn)
            xpfb = np.fft.fftshift(
                pfb_mask(x[nn],nchan_pfb,12, union_mask[nn], SKM, force_complex=True),axes=-1)
            ypfb = np.fft.fftshift(
                pfb_mask(y[nn],nchan_pfb,12, union_mask[nn], SKM, force_complex=True),axes=-1)
            #print(ypfb.size,np.sum(np.isnan(ypfb)))
            spec = (np.nanmean(np.abs(xpfb)**2,axis=0)\
                    +np.nanmean(np.abs(ypfb)**2,axis=0))/2
            #print(spec.size,np.sum(np.isnan(spec)))
            if np.sum(np.isnan(spec)) == 0:
                spectrum[nn*nchan_pfb:(nn+1)*nchan_pfb] += np.flip(spec[::-1])
                unflagged_blocks[nn*nchan_pfb:(nn+1)*nchan_pfb] += 1
            #print(spectrum.size, T.np.sum(np.isnan(spectrum)))

    spectrum /= unflagged_blocks
    #print(spectrum.size,np.sum(np.isnan(spectrum)))
    pfb_chanbw = chanbw/nchan_pfb
    #freqs = chanfreqs[0]-0.5*pfb_chanbw+np.arange(nchan_pfb*nchan)*pfb_chanbw
    freqs = fctr - 0.5*bw + bw/(nchan*nchan_pfb)*np.arange(nchan*nchan_pfb)
    #bad_chans = np.arange(nchan)*nchan_pfb + nchan_pfb//2
    #mask = np.zeros(spectrum.shape)
    #mask[bad_chans] = 1
    #masked_spectrum = np.ma.masked_array(spectrum,mask)
    out1 = (freqs,spectrum)
    #out2 = (freqs,masked_spectrum)
#     basenm = os.path.basename(infile)
    with open(os.path.join('/data/scratch/IQRMresults',basenm.replace(".raw",f"mask.{resolution}.spec.pkl")),"wb") as f: 
        pickle.dump(out1,f)
        print(f)
    self._pkl_filename = f
    #with open(os.path.join(args.outdir,basenm.replace(".raw",".20.spec_mask.pkl")), "wb") as f: 
    #    pickle.dump(out2,f)



#do fine channelization using a mask
def raw2spec_god(resolution,gr, det,outfile,mask=None):

    hdr0 = gr.read_first_header()
    fctr = float(hdr0["OBSFREQ"])
    bw = float(hdr0["OBSBW"])
    nchan = int(hdr0["OBSNCHAN"])
    chanbw = bw/nchan
    chanfreqs = fctr - 0.5*bw + chanbw*(np.arange(nchan)+0.5)
    nchan_pfb = 2**int(np.round(np.log2(np.abs(chanbw/(resolution/1e3)))))
    print(f'given output res is {resolution} kHz, actual will be {np.abs(chanbw/nchan_pfb)*1e3} khz')

    print(det)
    if mask is not None:
        if (det == 'AOF') or (det == 'MAD'):
            f = glob.glob(mask)
            f.sort()
            if len(f) != gr.n_blocks:
                print(f'There are {numblocks} blocks and you set -mb {mb}, pick a divisible integer')
                sys.exit()
        else:
            f = np.load(mask)

    spectrum = np.zeros(nchan_pfb*nchan)
    unflagged_blocks = np.zeros(nchan_pfb*nchan)

    gr.reset_index()
    for bb in range(gr.n_blocks):
        print(f"Working on block {bb+1} of {gr.n_blocks}")
        hdr,data = gr.read_next_data_block()
        x = data[:,:,0]
        y = data[:,:,1]

        #apply mask
        #find M
        #M = int((x.shape[1]*gr.n_blocks) / SKf.shape[1])
        #pulse = np.ones((1,M,1))
        #num_fbins = f.shape[1]//gr.n_blocks

        if (det == 'AOF') or (det == 'MAD'):
            mask = np.load(f[bb])
        else:
            num_fbins = f.shape[1]//gr.n_blocks
            mask = f[:,bb*num_fbins:(bb+1)*num_fbins,:]

        #mask = np.kron(this_f,pulse)

        union_mask = np.copy(mask[:,:,0])
        union_mask[mask[:,:,1]==1] = 1

        xma = np.ma.masked_array(x,union_mask)
        yma = np.ma.masked_array(y,union_mask)

        for nn in range(data.shape[0]):

            if mask is not None:
                xpfb = np.fft.fftshift(pfb_mask(xma[nn],nchan_pfb,12, force_complex=True),axes=-1)
                ypfb = np.fft.fftshift(pfb_mask(yma[nn],nchan_pfb,12, force_complex=True),axes=-1)

                spec = (np.nanmean(np.abs(xpfb)**2,axis=0)\
                    +np.nanmean(np.abs(ypfb)**2,axis=0))/2

                if np.sum(np.isnan(spec)) == 0:
                    spectrum[nn*nchan_pfb:(nn+1)*nchan_pfb] += np.flip(spec[::-1])
                    unflagged_blocks[nn*nchan_pfb:(nn+1)*nchan_pfb] += 1

            else:
                xpfb = np.fft.fftshift(pfb(x[nn],nchan_pfb,12,force_complex=True),axes=-1)
                ypfb = np.fft.fftshift(pfb(y[nn],nchan_pfb,12,force_complex=True),axes=-1)
                spec = (np.mean(np.abs(xpfb)**2,axis=0)\
                    +np.mean(np.abs(ypfb)**2,axis=0))/2

                spectrum[nn*nchan_pfb:(nn+1)*nchan_pfb] += np.flip(spec[::-1])

    if (det == 'AOF') or (det == 'MAD'):
        spectrum /= unflagged_blocks
    else:
        spectrum /= gr.n_blocks

    pfb_chanbw = chanbw/nchan_pfb

    freqs = fctr - 0.5*bw + bw/(nchan*nchan_pfb)*np.arange(nchan*nchan_pfb)

    out1 = (freqs,spectrum)
    with open(outfile,"wb") as outf: 
        pickle.dump(out1,outf)
        print(outf)
    #self._pkl_filename = outf






def reduce_pulsar_data(raw_file, output_dir):
#     #need to do lots of bookkeeping to put stuff in the right directories


#not sure if this is worth doing. requires psrenv and then copying the right par files, dm/period etc.


    pass



















