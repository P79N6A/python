#!/usr/bin/env python


#############################################################################
##
## Copyright (C) 2010 Hans-Peter Jansen <hpj@urpla.net>.
## Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).
## All rights reserved.
##
## This file is part of the examples of py_Qt.
##
## $QT_BEGIN_LICENSE:BSD$
## You may use this file under the terms of the BSD license as follows:
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are
## met:
##   * Redistributions of source code must retain the above copyright
##     notice, this list of conditions and the following disclaimer.
##   * Redistributions in binary form must reproduce the above copyright
##     notice, this list of conditions and the following disclaimer in
##     the documentation and/or other materials provided with the
##     distribution.
##   * Neither the name of Nokia Corporation and its Subsidiary(-ies) nor
##     the names of its contributors may be used to endorse or promote
##     products derived from this software without specific prior written
##     permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
## "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
## LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
## A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
## OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
## SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
## LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
## DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
## THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
## (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
## OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
## $QT_END_LICENSE$
##
#############################################################################


# This is only needed for Python v2 but is harmless for Python v3.
import sip
sip.setapi('QString', 2)

from PyQt4 import QtCore, QtGui


class FinalWidget(QtGui.QFrame):

    def __init__(self, parent, name, labelSize):
        super(FinalWidget, self).__init__(parent)

        self.dragStartPosition = QtCore.QPoint()

        self.hasImage = False
        self.imageLabel = QtGui.QLabel()
        self.imageLabel.setFrameShadow(QtGui.QFrame.Sunken)
        self.imageLabel.setFrameShape(QtGui.QFrame.StyledPanel)
        self.imageLabel.setMinimumSize(labelSize)
        self.nameLabel = QtGui.QLabel(name)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.imageLabel, 1)
        layout.addWidget(self.nameLabel, 0)
        self.setLayout(layout)

    def mouseMoveEvent(self, event):
        """ If the mouse moves far enough when the left mouse button is held
            down, start a drag and drop operation.
        """
        if not event.buttons() & QtCore.Qt.LeftButton:
            return

        if (event.pos() - self.dragStartPosition).manhattanLength() \
             < QtGui.QApplication.startDragDistance():
            return

        if not self.hasImage:
            return

        drag = QtGui.QDrag(self)
        mimeData = QtCore.QMimeData()

        output = QtCore.QByteArray()
        outputBuffer = QtCore.QBuffer(output)
        outputBuffer.open(QtCore.QIODevice.WriteOnly)
        self.imageLabel.pixmap().toImage().save(outputBuffer, 'PNG')
        outputBuffer.close()
        mimeData.setData('image/png', output)

        drag.setMimeData(mimeData)
        drag.setPixmap(self.imageLabel.pixmap().scaled(64, 64, QtCore.Qt.KeepAspectRatio))
        drag.setHotSpot(QtCore.QPoint(drag.pixmap().width() / 2,
                                      drag.pixmap().height()))
        drag.start()

    def mousePressEvent(self, event):
        """ Check for left mouse button presses in order to enable drag and
            drop.
        """
        if event.button() == QtCore.Qt.LeftButton:
            self.dragStartPosition = event.pos()

    def pixmap(self):
        return self.imageLabel.pixmap()

    def setPixmap(self, pixmap):
        self.imageLabel.setPixmap(pixmap)
        self.hasImage = True


class ScreenWidget(QtGui.QFrame):
    # Separation.
    Cyan, Magenta, Yellow = range(3)

    convertMap = {
        Cyan: QtGui.qRed,
        Magenta: QtGui.qGreen,
        Yellow: QtGui.qBlue,
    }

    imageChanged = QtCore.pyqtSignal()

    def __init__(self, parent, initialColor, name, mask, labelSize):
        """ Initializes the paint color, the mask color (cyan, magenta,
            or yellow), connects the color selector and invert checkbox to functions,
            and creates a two-by-two grid layout.
        """
        super(ScreenWidget, self).__init__(parent)

        self.originalImage = QtGui.QImage()
        self.newImage = QtGui.QImage()

        self.paintColor = initialColor
        self.maskColor = mask
        self.inverted = False

        self.imageLabel = QtGui.QLabel()
        self.imageLabel.setFrameShadow(QtGui.QFrame.Sunken)
        self.imageLabel.setFrameShape(QtGui.QFrame.StyledPanel)
        self.imageLabel.setMinimumSize(labelSize)

        self.nameLabel = QtGui.QLabel(name)
        self.colorButton = QtGui.QPushButton("Modify...")
        self.colorButton.setBackgroundRole(QtGui.QPalette.Button)
        self.colorButton.setMinimumSize(32, 32)

        palette = QtGui.QPalette(self.colorButton.palette())
        palette.setColor(QtGui.QPalette.Button, initialColor)
        self.colorButton.setPalette(palette)

        self.invertButton = QtGui.QPushButton("Invert")
        self.invertButton.setEnabled(False)

        self.colorButton.clicked.connect(self.setColor)
        self.invertButton.clicked.connect(self.invertImage)

        gridLayout = QtGui.QGridLayout()
        gridLayout.addWidget(self.imageLabel, 0, 0, 1, 2)
        gridLayout.addWidget(self.nameLabel, 1, 0)
        gridLayout.addWidget(self.colorButton, 1, 1)
        gridLayout.addWidget(self.invertButton, 2, 1, 1, 1)
        self.setLayout(gridLayout)

    def createImage(self):
        """ Creates a new image by separating out the cyan, magenta, or yellow
            component, depending on the mask color specified in the constructor.
            The amount of the component found in each pixel of the image is used
            to determine how much of a user-selected ink is used for each pixel
            in the new image for the label widget.
        """
        self.newImage = newImage = self.originalImage.copy()

        # Create CMY components for the ink being used.
        cyanInk = float(255 - QtGui.QColor(self.paintColor).red()) / 255.0
        magentaInk = float(255 - QtGui.QColor(self.paintColor).green()) / 255.0
        yellowInk = float(255 - QtGui.QColor(self.paintColor).blue()) / 255.0

        convert = self.convertMap[self.maskColor]

        for y in range(newImage.height()):
            for x in range(newImage.width()):
                p = self.originalImage.pixel(x, y)

                # Separate the source pixel into its cyan component.
                if self.inverted:
                    amount = convert(p)
                else:
                    amount = 255 - convert(p)

                newColor = QtGui.QColor(
                    255 - min(int(amount * cyanInk), 255),
                    255 - min(int(amount * magentaInk), 255),
                    255 - min(int(amount * yellowInk), 255))

                newImage.setPixel(x, y, newColor.rgb())

        self.imageLabel.setPixmap(QtGui.QPixmap.fromImage(newImage))

    def image(self):
        """ Returns a reference to the modified image. """
        return self.newImage

    def invertImage(self):
        """ Sets whether the amount of ink applied to the canvas is to be
            inverted (subtracted from the maximum value) before the ink is
            applied.
        """
        self.inverted = not self.inverted
        self.createImage()
        self.imageChanged.emit()

    def setColor(self):
        """ Separate the current image into cyan, magenta, and yellow
            components.  Create a representation of how each component might
            appear when applied to a blank white piece of paper.
        """
        newColor = QtGui.QColorDialog.getColor(self.paintColor)

        if newColor.isValid():
            self.paintColor = newColor
            palette = QtGui.QPalette(self.colorButton.palette())
            palette.setColor(QtGui.QPalette.Button, self.paintColor)
            self.colorButton.setPalette(palette)
            self.createImage()
            self.imageChanged.emit()

    def setImage(self, image):
        """ Records the original image selected by the user, creates a color
            separation, and enables the invert image checkbox.
        """
        self.originalImage = image
        self.createImage()
        self.invertButton.setEnabled(True)


class Viewer(QtGui.QMainWindow):
    # Brightness.
    Gloom, Quarter, Half, ThreeQuarters, Full = range(5)

    # Brightness value map.
    brightnessValueMap = {
        Gloom: 0,
        Quarter: 64,
        Half: 128,
        ThreeQuarters: 191,
        Full: 255,
    }

    def __init__(self):
        """ Constructor initializes a default value for the brightness, creates
            the main menu entries, and constructs a central widget that contains
            enough space for images to be displayed.
        """
        super(Viewer, self).__init__()

        self.scaledImage = QtGui.QImage()
        self.menuMap = {}
        self.path = ''
        self.brightness = 255

        self.setWindowTitle("QImage Color Separations")

        self.createMenus()
        self.setCentralWidget(self.createCentralWidget())

    def createMenus(self):
        """ Creates a main menu with two entries: a File menu, to allow the image
            to be selected, and a Brightness menu to allow the brightness of the
            separations to be changed.
            Initially, the Brightness menu items are disabled, but the first entry in
            the menu is checked to reflect the default brightness.
        """
        self.fileMenu = QtGui.QMenu("&File", self)
        self.brightnessMenu = QtGui.QMenu("&Brightness", self)

        self.openAction = self.fileMenu.addAction("&Open...")
        self.openAction.setShortcut(QtGui.QKeySequence('Ctrl+O'))
        self.saveAction = self.fileMenu.addAction("&Save...")
        self.saveAction.setShortcut(QtGui.QKeySequence('Ctrl+S'))
        self.saveAction.setEnabled(False)
        self.quitAction = self.fileMenu.addAction("E&xit")
        self.quitAction.setShortcut(QtGui.QKeySequence('Ctrl+Q'))

        self.noBrightness = self.brightnessMenu.addAction("&0%")
        self.noBrightness.setCheckable(True)
        self.quarterBrightness = self.brightnessMenu.addAction("&25%")
        self.quarterBrightness.setCheckable(True)
        self.halfBrightness = self.brightnessMenu.addAction("&50%")
        self.halfBrightness.setCheckable(True)
        self.threeQuartersBrightness = self.brightnessMenu.addAction("&75%")
        self.threeQuartersBrightness.setCheckable(True)
        self.fullBrightness = self.brightnessMenu.addAction("&100%")
        self.fullBrightness.setCheckable(True)

        self.menuMap[self.noBrightness] = self.Gloom
        self.menuMap[self.quarterBrightness] = self.Quarter
        self.menuMap[self.halfBrightness] = self.Half
        self.menuMap[self.threeQuartersBrightness] = self.ThreeQuarters
        self.menuMap[self.fullBrightness] = self.Full

        self.currentBrightness = self.fullBrightness
        self.currentBrightness.setChecked(True)
        self.brightnessMenu.setEnabled(False)

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.brightnessMenu)

        self.openAction.triggered.connect(self.chooseFile)
        self.saveAction.triggered.connect(self.saveImage)
        self.quitAction.triggered.connect(QtGui.qApp.quit)
        self.brightnessMenu.triggered.connect(self.setBrightness)

    def createCentralWidget(self):
        """ Constructs a central widget for the window consisting of a two-by-two
            grid of labels, each of which will contain an image. We restrict the
            size of the labels to 256 pixels, and ensure that the window cannot
            be resized.
        """
        frame = QtGui.QFrame(self)
        grid = QtGui.QGridLayout(frame)
        grid.setSpacing(8)
        grid.setMargin(4)

        self.layout().setSizeConstraint(QtGui.QLayout.SetFixedSize)

        labelSize = QtCore.QSize(256, 256)

        self.finalWidget = FinalWidget(frame, "Final image", labelSize)

        self.cyanWidget = ScreenWidget(frame, QtCore.Qt.cyan, "Cyan",
                ScreenWidget.Cyan, labelSize)
        self.magentaWidget = ScreenWidget(frame, QtCore.Qt.magenta, "Magenta",
                ScreenWidget.Magenta, labelSize)
        self.yellowWidget = ScreenWidget(frame, QtCore.Qt.yellow, "Yellow",
                ScreenWidget.Yellow, labelSize)

        self.cyanWidget.imageChanged.connect(self.createImage)
        self.magentaWidget.imageChanged.connect(self.createImage)
        self.yellowWidget.imageChanged.connect(self.createImage)

        grid.addWidget(self.finalWidget, 0, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
        grid.addWidget(self.cyanWidget, 0, 1, QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
        grid.addWidget(self.magentaWidget, 1, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
        grid.addWidget(self.yellowWidget, 1, 1, QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)

        return frame

    def chooseFile(self):
        """ Provides a dialog window to allow the user to specify an image file.
            If a file is selected, the appropriate function is called to process
            and display it.
        """
        imageFile = QtGui.QFileDialog.getOpenFileName(self,
                "Choose an image file to open", self.path, "Images (*.*)")

        if imageFile != '':
            self.openImageFile(imageFile)
            self.path = imageFile

    def setBrightness(self, action):
        """ Changes the value of the brightness according to the entry selected in the
            Brightness menu. The selected entry is checked, and the previously selected
            entry is unchecked.
            The color separations are updated to use the new value for the brightness.
        """
        if action not in self.menuMap or self.scaledImage.isNull():
            return

        self.brightness = self.brightnessValueMap.get(self.menuMap[action])
        if self.brightness is None:
            return

        self.currentBrightness.setChecked(False)
        self.currentBrightness = action
        self.currentBrightness.setChecked(True)

        self.createImage()

    def openImageFile(self, imageFile):
        """ Load the image from the file given, and create four pixmaps based
            on the original image.
            The window caption is set, and the Brightness menu enabled if the image file
            can be loaded.
        """
        originalImage = QtGui.QImage()

        if originalImage.load(imageFile):
            self.setWindowTitle(imageFile)
            self.saveAction.setEnabled(True)
            self.brightnessMenu.setEnabled(True)

            self.scaledImage = originalImage.scaled(256, 256, QtCore.Qt.KeepAspectRatio)

            self.cyanWidget.setImage(self.scaledImage)
            self.magentaWidget.setImage(self.scaledImage)
            self.yellowWidget.setImage(self.scaledImage)
            self.createImage()
        else:
            QtGui.QMessageBox.warning(self, "Cannot open file",
                    "The selected file could not be opened.",
                    QtGui.QMessageBox.Cancel, QtGui.QMessageBox.NoButton,
                    QtGui.QMessageBox.NoButton)

    def createImage(self):
        """ Creates an image by combining the contents of the three screens
            to present a page preview.
            The image associated with each screen is separated into cyan,
            magenta, and yellow components. We add up the values for each
            component from the three screen images, and subtract the totals
            from the maximum value for each corresponding primary color.
        """
        newImage = self.scaledImage.copy()

        image1 = self.cyanWidget.image()
        image2 = self.magentaWidget.image()
        image3 = self.yellowWidget.image()
        darkness = 255 - self.brightness

        for y in range(newImage.height()):
            for x in range(newImage.width()):
                # Create three screens, using the quantities of the source CMY
                # components to determine how much of each of the inks are to
                # be put on each screen.
                p1 = image1.pixel(x, y)
                cyan1 = float(255 - QtGui.qRed(p1))
                magenta1 = float(255 - QtGui.qGreen(p1))
                yellow1 = float(255 - QtGui.qBlue(p1))

                p2 = image2.pixel(x, y)
                cyan2 = float(255 - QtGui.qRed(p2))
                magenta2 = float(255 - QtGui.qGreen(p2))
                yellow2 = float(255 - QtGui.qBlue(p2))

                p3 = image3.pixel(x, y)
                cyan3 = float(255 - QtGui.qRed(p3))
                magenta3 = float(255 - QtGui.qGreen(p3))
                yellow3 = float(255 - QtGui.qBlue(p3))

                newColor = QtGui.QColor(
                    max(255 - int(cyan1 + cyan2 + cyan3) - darkness, 0),
                    max(255 - int(magenta1 + magenta2 + magenta3) - darkness, 0),
                    max(255 - int(yellow1 + yellow2 + yellow3) - darkness, 0))

                newImage.setPixel(x, y, newColor.rgb())

        self.finalWidget.setPixmap(QtGui.QPixmap.fromImage(newImage))

    def saveImage(self):
        """ Provides a dialog window to allow the user to save the image file.
        """
        imageFile = QtGui.QFileDialog.getSaveFileName(self,
                "Choose a filename to save the image", "", "Images (*.png)")

        info = QtCore.QFileInfo(imageFile)

        if info.baseName() != '':
            newImageFile = QtCore.QFileInfo(info.absoluteDir(),
                    info.baseName() + '.png').absoluteFilePath()

            if not self.finalWidget.pixmap().save(newImageFile, 'PNG'):
                QtGui.QMessageBox.warning(self, "Cannot save file",
                        "The file could not be saved.",
                        QtGui.QMessageBox.Cancel, QtGui.QMessageBox.NoButton,
                        QtGui.QMessageBox.NoButton)
        else:
            QtGui.QMessageBox.warning(self, "Cannot save file",
                    "Please enter a valid filename.", QtGui.QMessageBox.Cancel,
                    QtGui.QMessageBox.NoButton, QtGui.QMessageBox.NoButton)


if __name__ == '__main__':

    import sys

    app = QtGui.QApplication(sys.argv)
    window = Viewer()
    window.show()
    sys.exit(app.exec_())