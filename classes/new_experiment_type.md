I want to create a new experiment type: MotFluorescenceAlignment.

This experiment should function similar to a sweep, but rather than running different MotFluoresceExperiments it should run the same experiment over and over again until the user chooses to stop the alignment.

This will need a new configuration object to be created and a new config reader to extract the data from a config file.

The point of this experiment is to allow the physical experimental setup to be altered in real time to improve the experimental results. Because of this, the way the experiment should run is it should run a single shot (with eg. 7 iterations, defined in the experiment config file) and then instantly display the result of that experiment, with a number calculated from the data analysis code. This number should be clearly visible for a while so the experimenter can tell whether their changes improved or worsened the results. This should keep repeating until the experimenter determines that the experiment is sufficiently optimised and can choose to stop the experiment.
