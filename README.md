This version of the RAP control software is built ontop of a python SDK supplied by Allied Vision and has javascript (for the terminal command line interface) and and c++ (for controlling the Arduino microcontroller).

<b> Before getting started, download the following if needed:</b>

1) Python: https://www.python.org/downloads/windows/
2) Node js: https://nodejs.org/en/download/
3)  (vimba-x 64 bit): https://www.1stvision.com/cameras/Allied-Vision-Vimba-X-software#
4) Vimba python libraries: https://github.com/alliedvision/VmbPy (follow the installation instructions on the github page).
5) Arduino IDE : https://www.arduino.cc/en/software/

Ensure that <b> python, pip, node,</b> and <b> npm </b> are all configured to be on your path (i.e. callable from the command line).

You may also need a text or code editor (e.g. vscode, or texpad: https://www.textpad.com/home for PCs)

Once you've downloaded the software in this repository, read the instructions in the 'docs' directory to finish the install.

guide to starting (all in terminal):

installing requirements:
pip install -r requirements.txt
npm install

running tests:
pytest
npm test

'pytest' tests the functionality in the vimba_rap3.py file while 'npm test' tests the interactivecls.js file. These two make up the
majority of the "thinking" in the project.
