# igi2-tex-viewer

a simple texture viewer written in python with pyside6 for gui and pil to handle image processing. this tool is specifically designed to view texture files from *igi 2: covert strike* stored in `.res` files. it supports `.tex` and `.tga` image formats and provides functionality to extract and view these images interactively

![screenshot](https://cdn.discordapp.com/attachments/905489045512130560/1290242268174876714/image.png)

## features

- **gui based viewer**: interface built using pyside6
- **support for .res files**: parses `.res` resource files and displays their content
- **image handling**: uses `pil` (pillow) library to manipulate and display images
- **console debugging**: toggle the internal console to view logs and debug output
- **image export**: double-click on an image to save it in `.tga` format
- **responsive design**: adapts the image display to the current window size

## requirements

- python 3.6+
- pyside6 (`pip install pyside6`)
- pil (`pip install pillow`)

## installation

1. clone the repository:

    ```bash
    git clone https://github.com/remivoire/igi2-tex-viewer.git
    ```

2. navigate to the project directory:

    ```bash
    cd igi2-tex-viewer
    ```

3. install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## usage

1. run the script:

    ```bash
    python ilff_pyside6.py
    ```

2. use the `file -> open` menu to load a `.res` file containing textures

3. browse through the available textures using the list on the left

4. double-click on any image to save it in `.tga` format

## keyboard shortcuts

- **ctrl+o**: open a `.res` file
- **ctrl+d**: toggle the console view
- **esc**: exit the application

## supported formats

- **.tex**: custom format used in igi 2 for storing textures
- **.tga**: standard tga (targa) image format for viewing and exporting textures

## known issues

- some `.tex` files with unusual sizes or formats might not display correctly
- specific textures in the resource file might fail to load

