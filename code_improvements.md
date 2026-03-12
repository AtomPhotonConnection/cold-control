The goal of this code is to have an easy to maintain codebase for running cold atom physics
experiments. It should be easy to maintain so that if anything breaks it can be easily fixed.
It should be modular so that different parts of the codebase can be used for different experiments.
And it should be clear what each part of the code is doing so that if changes need to be 
made then this can be done quickly and easily.

## Suggested changes
1. The sequence UI is very complicated and a bit dodgy. It should be simplified and made so that all the channels can be easily turned on and off and removed from the legend (otherwise the legend gets too big to fit in the window).

2. There should be some kind of test scripts that allow a config file to be tested to see if it will work properly.

3. Any additional changes here...