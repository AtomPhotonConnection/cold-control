# New structure for the pulse shape optimisation

## Classes

**Pulse Shape Experiment runner class**
 - Takes 2 inputs: A pulse shape experiment config object (that specifies relevant experiment parameters) and a waveform object that specifies the waveform to be played on the channel seeking to be calibrated
 - Then the class should have a run() method that scales the waveform to the right level, writes the waveform to the AWG, plays the AWG signal, records the result from the scope etc. Essentially this should run the whole physical experiment.
 - The run() method should return a pulse shape experiment result object that contains all relevant details of the experimental run

**Pulse shape experiment result class**
 - Created by the experiment runner class
 - Has (among other things) properties like mean squared error (the difference between the theoretically desired pulse and the actual pulse), an array containing the signed error at every sample, etc.
 - Has a plotting method. This should enable the production of a plot containing the signal sent to the awg, the signal measured by the scope, and the theoretically desired signal. These should be on the same axes and scaled so they are all visible.

**Pulse shape config class**
 - This should have a method to extract the properties from the path to a .ini file containing the relevant experimental parameters.
 - This config will then be passed to the experiment runner class


## Optimisation

Rather than the optimisation happening in the experiment itself, I want to create a setup where I can run an experiment with a particular waveform, then use the result object to calculate a new optimal waveform, then run a new experiment with the calculated waveform to test out how good it is. This should happen in a separate script so I can try out a variety of optimisation techniques.