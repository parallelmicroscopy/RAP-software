This version of the RAP control software is built ontop of a python SDK supplied by Allied Vision and has javascript (for the terminal command line interface) and and c++ (for controlling the Arduino microcontroller).

<i> For Hardware </i> see: https://github.com/parallelmicroscopy/24-well-RAP-hardware

### Before downloading the RAP software, install:

1) Python: https://www.python.org/downloads/windows/
2) Node js: https://nodejs.org/en/download/
3)  (vimba-x 64 bit): https://www.1stvision.com/cameras/Allied-Vision-Vimba-X-software#
4) Vimba python libraries: https://github.com/alliedvision/VmbPy
    <br>
    (follow the installation instructions on the github page).
6) Arduino IDE : https://www.arduino.cc/en/software/

Ensure that <b> python, pip, node,</b> and <b> npm </b> are all configured to be on your path (i.e. callable from the command line).

You may also need a text or code editor (e.g. vscode, or texpad: https://www.textpad.com/home for PCs)

### Download the software in this repository
```
git clone https://github.com/parallelmicroscopy/RAP-software
```
<i>or</i>

navigate to the green 'code' button, 'download as zip' and decompress the files in your 'documents' folder.

### Setup instructions

Once you've downloaded the software, read the instructions in the 'docs' directory.

#### Arduino instructions:
Open the arduino ide, and upload 'RAP_Alberta_Fastled.ino' to your Arduino Uno card.


#### Download additional dependencies and requirements:

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
