This page is for downloading and installing the **software** for controlling RAP (parallel) microscopes. 

- For a general **introduction and overview** see: https://github.com/parallelmicroscopy/overview
- For **hardware** see: https://github.com/parallelmicroscopy/24-well-RAP-hardware

The RAP ontrol software is built ontop of a python / openCV SDK supplied by Allied Vision and has javascript (for the terminal command line interface) and and c++ (for controlling the Arduino microcontroller).

### 1) Install these packages if you don't have them:

- Python: https://www.python.org/downloads/windows/
- Node js: https://nodejs.org/en/download/
- Vimba-x (64 bit): https://www.1stvision.com/cameras/Allied-Vision-Vimba-X-software#
- Vimba python libraries: https://github.com/alliedvision/VmbPy
- Arduino IDE : https://www.arduino.cc/en/software/

Ensure that <b> python, pip, node,</b> and <b> npm </b> are all configured to be on your path (i.e. callable from the command line).

You may also need a text or code editor (e.g. vscode, or texpad: https://www.textpad.com/home for PCs).

### 2) Download the microscope control software from this repository:

Either:

```
git clone https://github.com/parallelmicroscopy/RAP-software
```
<i>or</i>

navigate to the green 'code' button, 'download as zip' and decompress the files in your 'documents' folder.

### 3) Setup the microscope control software:

Once you've downloaded the software, read the instructions in the 'docs' directory, and a) upload software to the Ardnuino microcontroller; and b) download additional dependences.

#### a) Arduino instructions:
Open the arduino ide, and upload 'RAP_Alberta_Fastled.ino' to your Arduino Uno card.
<br>
The software uses the FastLED.h (https://github.com/FastLED/FastLED) library set for a 24 array of Dotstar (https://learn.adafruit.com/adafruit-dotstar-leds/overview) LEDs.  If you use a different LED type (e.g. Neopixels, as was used in the original eLife publication)  or array size, *you will have to make minor changes to the microcontroller .ino (c++) file*.


#### b) Download additional dependencies and requirements:

The python and javascript programs use several public packages that can be downloaded and installed using <b>pip</b> and <b>npm</b>.

<b> From the terminal: </b>

```
pip install -r requirements.txt
npm install
```
running tests:
```
pytest
npm test
```
'pytest' tests the functionality in the vimba_rap3.py file while 'npm test' tests the interactivecls.js file. These two programs do the majority of the work.
