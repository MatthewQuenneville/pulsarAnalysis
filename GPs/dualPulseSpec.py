#!/usr/bin/env python

import sys
import numpy as np
import matplotlib.pylab as plt
import pulsarAnalysis.GPs.pulseFinder as pf
import pulsarAnalysis.GPs.pulseSpec as ps

# Time to display before pulse peak in seconds
leadWidth=0.0001

# Time to display after pulse peak in seconds
trailWidth=0.0003

# Resolution to use for searching in seconds. Must be larger than or
# equal to phase bin size.
searchRes=1.0/10000

# Use same intensity color scale
sameColorScale=False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print "Usage: %s foldspec1 foldspec2" % sys.argv[0]
        # Run the code as eg: ./dualPulseSpec.py foldspec1.npy foldspec2.py.
        sys.exit(1)
    
    # Declare observation list, and dynamic spectra, frequency band,
    # pulse time, and RFI-free channel dictionaries
    obsList=[]
    dynamicSpec={}
    freqBand={}
    pulseTimes={}
    cleanChans={}
    tRange={}

    # Loop through JB and GMRT files
    for ifilename in sys.argv[1:]:
        
        # Folded spectrum axes: time, frequency, phase, pol=4 (XX, XY, YX, YY).

        # Get run information
        deltat=pf.getDeltaT(ifilename)
        telescope=pf.getTelescope(ifilename)
        startTime=pf.getStartTime(ifilename)
        obsList.append((startTime,telescope))
        freqBand[obsList[-1]]=pf.getFrequencyBand(telescope)

        if 'foldspec' in ifilename:
            f = np.load(ifilename)
            ic = np.load(ifilename.replace('foldspec', 'icount'))

            # Collapse time axis
            f=f[0,...]
            ic=ic[0,...]

            # Find populated bins
            fullList=np.flatnonzero(ic.sum(0))
            w=f/ic[...,np.newaxis]

            binWidth=deltat/f.shape[1]

        elif 'waterfall' in ifilename:
            w=np.load(ifilename)
            w=np.swapaxes(w,0,1)
            fullList=range(w.shape[1])
            binWidth=pf.getWaterfallBinWidth(telescope,w.shape[0])

        else:
            print "Error, unrecognized file type."
            sys.exit()

        # Check for polarization data
        if not w.shape[-1]==4:
            print "Error, polarization data is missing for "+telescope+"."
            sys.exit()

        # Rebin to find giant pulses
        nSearchBins=min(w.shape[1],int(round(deltat/searchRes)))
    
        w_rebin=pf.rebin(w,nSearchBins)
        timeSeries_rebin=pf.getTimeSeries(w_rebin)
        timeSeries=pf.getTimeSeries(w)
        pulseList=pf.getPulses(timeSeries_rebin,binWidth=searchRes)
        if nSearchBins<w.shape[1]:
            pulseList=[(pf.resolvePulse(
                        timeSeries,int(pos*w.shape[1]/nSearchBins),
                        binWidth=binWidth,searchRadius=1.0/10000),height) 
                       for (pos,height) in pulseList]
        try:
            largestPulse=pulseList[0][0]
        except IndexError:
            print "Error, no giant pulse found in "+telescope+" for start time:"
            print startTime.iso
            sys.exit

        # Find range of pulse to plot
        leadBins=int(leadWidth/binWidth)
        trailBins=int(trailWidth/binWidth)       
        pulseRange=range(largestPulse-leadBins,largestPulse+trailBins)
        offRange=range(largestPulse-2*leadBins-trailBins,largestPulse-leadBins)
        
        # Add entries to dynamic spectra and frequency band dictionaries
        bg=ps.dynSpec(w,indices=offRange,normChan=False).mean(1,keepdims=True)
        dynamicSpec[obsList[-1]]=ps.dynSpec(w,indices=pulseRange,
                                            normChan=False)-bg
                                            
        pulseTimes[obsList[-1]]=(pf.getTime(pulseList[0][0],binWidth,
                                            startTime).iso[:-3]).split()[-1]
        cleanChans[obsList[-1]]=ps.getRFIFreeBins(w.shape[0],telescope)
        tRange[obsList[-1]]=(-binWidth*leadBins,binWidth*trailBins)
        
    # Determine aspect ratio for plotting
    freqRange=[b-a for (a,b) in freqBand.values()]
    maxFreqRange=max(freqRange)
    aspect=2e6*(leadWidth+trailWidth)/maxFreqRange


    # Declare max and min z axis values for plotting
    vmin=[[],[]]
    vmax=[[],[]]
    
    for i in range(4):
        if sameColorScale:
            minVal=min([np.amin(dynamicSpec[iObs][cleanChans[iObs],:,i]) 
                     for iObs in obsList])
            maxVal=max([np.amax(dynamicSpec[iObs][cleanChans[iObs],:,i]) 
                     for iObs in obsList])
            vmin[0].append(minVal)
            vmax[0].append(maxVal)
            vmin[1].append(minVal)
            vmax[1].append(maxVal)
        else:
            for j,iObs in enumerate(obsList):
                vmin[j].append(np.amin(dynamicSpec[iObs][cleanChans[iObs],:,i]))
                vmax[j].append(np.amax(dynamicSpec[iObs][cleanChans[iObs],:,i]))
    if sameColorScale:
        minVal_sum=min([np.amin(
                    dynamicSpec[iObs][cleanChans[iObs],:,(0,3)].sum(-1)) 
                      for iObs in obsList])
        maxVal_sum=max([np.amax(
                    dynamicSpec[iObs][cleanChans[iObs],:,(0,3)].sum(-1)) 
                      for iObs in obsList])
        vmin_sum=[minVal_sum,minVal_sum]
        vmax_sum=[maxVal_sum,maxVal_sum]
    else:
        vmin_sum=[np.amin((dynamicSpec[iObs][cleanChans[iObs],...])[...,(0,3)].sum(-1)) for iObs in obsList]
        vmax_sum=[np.amax((dynamicSpec[iObs][cleanChans[iObs],...])[...,(0,3)].sum(-1)) for iObs in obsList]

    # Find difference in frequency range and channel widths
    upperDiff=freqBand[obsList[0]][1]-freqBand[obsList[1]][1]
    lowerDiff=freqBand[obsList[0]][0]-freqBand[obsList[1]][0]
    chanWidth=[]
    chanWidth.append(
        (freqBand[obsList[0]][1]-freqBand[obsList[0]][0])/
        dynamicSpec[obsList[0]].shape[0])
    chanWidth.append(
        (freqBand[obsList[0]][1]-freqBand[obsList[0]][0])/
        dynamicSpec[obsList[0]].shape[0])

    if not chanWidth[0]==chanWidth[1]:
        print "Warning, channel widths are not equal."

    # Pad smaller image with constant values to maintain aspect ratio
    if upperDiff>0:
        nBinsUpper=int(round(upperDiff/chanWidth[1]))
        dynamicSpec[obsList[1]]=np.pad(dynamicSpec[obsList[1]],
                                       ((0,nBinsUpper),(0,0),(0,0)),
                                       mode='constant',
                                       constant_values=
                                       ((0,vmin[1]),(0,0),(0,0)))
    elif upperDiff<0:
        nBinsUpper=int(round(-upperDiff/chanWidth[0]))
        dynamicSpec[obsList[0]]=np.pad(dynamicSpec[obsList[0]],
                                       ((0,nBinsUpper),(0,0),(0,0)),
                                       mode='constant',
                                       constant_values=
                                       ((0,vmin[0]),(0,0),(0,0)))
    if lowerDiff<0:
        nBinsLower=int(round(-lowerDiff/chanWidth[1]))
        dynamicSpec[obsList[1]]=np.pad(dynamicSpec[obsList[1]],
                                       ((nBinsLower,0),(0,0),(0,0)),
                                       mode='constant',
                                       constant_values=
                                       ((vmin[1],0),(0,0),(0,0)))
        cleanChans[obsList[1]]=[i+nBinsLower for i in cleanChans[obsList[1]]]
    elif lowerDiff>0:
        nBinsLower=int(round(lowerDiff/chanWidth[0]))
        dynamicSpec[obsList[0]]=np.pad(dynamicSpec[obsList[0]],
                                       ((nBinsLower,0),(0,0),(0,0)),
                                       mode='constant',
                                       constant_values=
                                       ((vmin[0],0),(0,0),(0,0)))
        cleanChans[obsList[0]]=[i+nBinsLower for i in cleanChans[obsList[1]]]

    # Loop through polarisations to plot
    for i in range(4):

        fig,axes = plt.subplots(nrows=1,ncols=2)
            
        ymin=min([ifreq[0] for ifreq in freqBand.values()])
        ymax=max([ifreq[1] for ifreq in freqBand.values()])

        # Loop through telescopes
        for j,jobs in enumerate(obsList):

            # Plot image and set titles
            im=axes.flat[j].imshow(dynamicSpec[jobs][:,:,i],origin='lower',
                       interpolation='nearest',cmap=plt.get_cmap('Greys'),
                       extent=[tRange[jobs][0]*1e6,tRange[jobs][1]*1e6,
                               ymin,ymax],
                       aspect=aspect,vmin=vmin[j][i],vmax=vmax[j][i])
            axes.flat[j].set_title(pulseTimes[jobs]+'\n'+jobs[1]+
                                   ' ( Pol '+str(i)+' )')
            axes.flat[j].set_xlabel('Time (microseconds)')
            axes.flat[j].set_ylabel('Frequency (MHz)')
            # Plot color bar on each subplot if color scales are different
            if not sameColorScale:
                plt.colorbar(im,ax=axes.flat[j])

        # Add single color bar if color scales are equal, otherwise
        # prevent overlap of colorbars with labels
        if sameColorScale:
            cax = fig.add_axes([0.9,0.1,0.03,0.8])
            fig.colorbar(im,cax=cax)
        else:
            plt.tight_layout()
        
        plt.show()

    fig,axes = plt.subplots(nrows=1,ncols=2)

    # Loop through telescopes
    for j,jobs in enumerate(obsList):
        
        # Plot image and set titles
        im=axes.flat[j].imshow(dynamicSpec[jobs][:,:,(0,3)].sum(-1),
                               origin='lower',
                               interpolation='nearest',
                               #cmap=plt.get_cmap('Greys'),
                               extent=[tRange[jobs][0]*1e6,tRange[jobs][1]*1e6,
                                       ymin,ymax],
                               aspect=aspect,
                               vmin=vmin_sum[j],
                               vmax=vmax_sum[j])
        axes.flat[j].set_title(pulseTimes[jobs]+'\n'+jobs[1]+
                               ' ( Intensity )')
        axes.flat[j].set_xlabel('Time (microseconds)')
        axes.flat[j].set_ylabel('Frequency (MHz)')
        if not sameColorScale:
            plt.colorbar(im,ax=axes.flat[j])
    if sameColorScale:
        cax = fig.add_axes([0.9,0.1,0.03,0.8])
        fig.colorbar(im,cax=cax)
    else:
        plt.tight_layout()
    
    plt.show()

    # Plot Spectra
    freqList=[]
    for j,jObs in enumerate(obsList):
        spectrum=(dynamicSpec[jObs][cleanChans[jObs],...])[...,(0,3)].sum(-1).sum(1)     
        spectrum=(spectrum-np.mean(spectrum))/np.std(spectrum)
        chanWidth=(ymax-ymin)/dynamicSpec[jObs].shape[0]
        freqList.append([ymin+chanWidth*i for i in cleanChans[jObs]])
        # Plot image and set titles
        plt.plot(freqList[-1],spectrum,label=jObs[1])
    xmin=max([min(i) for i in freqList])
    xmax=min([max(i) for i in freqList])
    plt.xlim(xmin,xmax)
    plt.legend()
    plt.xlabel('Frequency (MHz)')
    plt.ylabel('Intensity')
    plt.show()

    # Plot Profile
    timeList=[]
    for j,jObs in enumerate(obsList):
        profile=(dynamicSpec[jObs][cleanChans[jObs],...])[...,(0,3)].sum(-1).sum(0)     
        profile=(profile-np.mean(profile))/np.std(profile)
        timeList.append(np.linspace(tRange[jObs][0],tRange[jObs][1],len(profile))*1e6)
        # Plot image and set titles
        plt.plot(timeList[-1],profile,label=jObs[1])
    xmin=max([min(i) for i in timeList])
    xmax=min([max(i) for i in timeList])
    plt.xlim(xmin,xmax)
    plt.legend()
    plt.xlabel('Time (microseconds)')
    plt.ylabel('Intensity')
    plt.show()
