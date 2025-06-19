### zeroPad
1. Padding logic

### LEDS
1. array of correct length
2. Comprised of LED's with correct values

### generateDefaultExperiment
1. correct prefix and directory
2. Correct LED and set data
3. Correct shape in terms of wells and sets

### program.command
1. config command writes to correct files and as intended
2. save command correct number of files goes to correct directory
3. show command print correct well structure

### load_configuration
1. Makes custom config file and asserts its been loaded properly

### changeCurrentSet
1. creates custom LED's, selects them, runs function then declares they're in `exp.sets[0].wells` and it has the right defaults
2. If set values are specified, pushing new selected cells doesn't change those values

### copySetToTable (unfinished)
1. empty activeset -> selected cells is empty

### generateLEDList
1. Asserts default values and indexing logic

### assignLetter
1. Correct letter assignment with outside leading to *