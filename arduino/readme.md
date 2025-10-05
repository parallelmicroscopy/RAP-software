The  Arduino code assumes that you have an array of 24 dotstar LEDs arranged in a grid.  If you are instead using a Neopixel array, you will have to alter the code to account for the different pixel architecture and number. The software uses the FASTLED.h (https://github.com/FastLED/FastLED) library so these changes are straightforward.

Upload the code using your arduino IDE. You should only need to do this once. Instructions are passed between the Arduino and javascript programs occurs via serial communication.
