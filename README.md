# cold-control

This is the GUI used to control all aspects of the atomic cavity-QED physics experiments in our lab.  These styles of experiment tend to invlove many different instruments, all of which need to be managed in a coherent way. The aim of this GUI is to provide a interface to this system, where the user can focus on the desired experiment(s) without having to explicity consider how this is implemented on a hardware level.  This repository of course serves as a resource for myself and future group members to extend this work, but unfortunately an outside user can not expect to simply plug-and-play the GUI as it is specifically tailored to the set-up we have.  That said, if anyone has stumbled upon this when looking to implement some of the contained functionality into their own set-up, I would hope that the modular nature of the code is such that this can provide a reasonable starting point.

For a flavor of the work this underpins see the [Atom-Photon connection group website](https://www2.physics.ox.ac.uk/research/the-atom-photon-connection).

# Overview of the functionality

The below is not an exhaustive list and neglects most specfics, however it hopefully provides a pointer to the relevant code underlying the core functionality provided by cold-control.

  - A TkInter based interface for the experiment is run from [Root_UI](Root_UI.py).
  - DAQ cards write static voltages and play preceisely timed sequences to execute the experiment.  To this end the [DAQ](DAQ.py) (for the hardware interface) and [DAQ_UI](DAQ_UI.py) (for the GUI interface) modules contain the functionality to synchronise and control multiple ADLINK-2502 DAQ cards.  A calibration between these voltages and the functionality they control is also supported - for example an acousto-optic modulator (AOM) that controls the power and frequency of a given laser-line is far better interfaced with by requesting the desired power and frequency, rather than manually changing the voltage that drives it.
  - The data handling and an interface for custom sequences played on the DAQ cards to control a given experimental run are provided by [Sequence](Sequence.py) and [Sequence_UI](Sequence_UI.py).
  - Controlling all other aspects of the experimental run (automated staging of multiple experiments, data aquisition, on-the-fly analysis etc) are provided by the [ExperimentalRunner](ExperimentalRunner.py) and [Experimental_UI](Experimental_UI.py).

  - The [instruments](instruments) folder contains python wrappers to talk to various devices including:
    - [Tarbor Electronics WX218x AWG](instruments/WX218x)
    - [IC Imaging Control camera](instruments/pyicic)
    - [qutools quTAU TDC](instruments/quTAU) 
    - [ThorlabsPM100 powermeter](instruments/ThorlabsPM100)
    - [TF930 frequency counter](instruments/TF930)
    - Other instruments in this folder are not currently integrated with cold-control, however some work has been done on proving a wrapper for doing so and this is included.


# More detailed explanation for future users

N.B. These details are correct as of 27/10/2025, written by Matthew King. However, by the time you are reading this things might look very different.

The [calibrations_scripts](calibrations/calibration_scripts/) folder contains scripts used to run calibrations. These scripts are used to enable automatic conversion between desired quantities (such as modulation frequency, Rabi frequency, etc.) and experimental quantities (voltage, optical power, etc.). The data collected by these scripts is saved in the calibrations folder and used by the program when needed.

The [classes](classes/) folder contains classes used to manage the experiment. These include:
 - The classes to manage the [DAQ cards](classes/DAQ.py), from which the DAQ cards can be controlled individually
 - Classes to manage the [Experimental Configs](classes/ExperimentalConfigs.py). For example, a class like MotFluoresceConfig has all the configuration needed for a MOT Fluorescence experiment.
 - Classes to [run the experiments](classes/ExperimentalRunner.py). An instance of a config class (as defined in the experimental configs file) can be passed to one of the experimental runner classes and this will execute the experiment according to the specified parameters.
 - Classes to manage the [daq sequences](classes/Sequence.py). Rather than controlling each DAQ card individually, a sequence can be used to preload a set of DAQ values at different times, which can then be played.
 - Classes to [read the config files](classes/Config.py). As all the parameters for experiments are saved in config files, the config classes are used to read data from the config files and then use this to create a config object as defined in experimental configs.

The [configs](configs/) folder contains .ini files used to specify the configurations (or parameters for) a particular experiment. When a user creates a config file and uses it to run an experiment, the process is as follows:
User creates config file -> Config file read by Config.py class -> Parameters loaded into ExperimentalConfigs.py class -> Experiment executed by ExperimentalRunner.py class

The [data_analysis_functions](data_analysis_functions/) folder contains scripts to analyse the data from particular experiments.

The [instruments](instruments) folder is as described above.

The [lab_control_functions](lab_control_functions/) folder contains files with functions and classes to allow the control of multiple instruments in the lab.

The [UI_classes](UI_classes/) folder contains classes that manage the UI elements. These are relied upon by Root_UI.py to manage the UI as a whole, given there are different components to the UI including the part used to control individual DAQ cards ([DAQ_UI](UI_classes/DAQ_UI.py)); the part used to run experiments ([Experimental_UI](UI_classes/Experimental_UI.py)); and the part used to view and change sequences ([Sequence_UI](UI_classes/Sequence_UI.py)).

The [waveforms](waveforms/) folder contains .csv files that give voltages as a function of time. These files can be referenced in configuration files as waveforms to be loaded to the AWG that will then by played at a particular point in the experiment.


