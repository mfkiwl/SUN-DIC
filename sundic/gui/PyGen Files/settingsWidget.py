# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'settingsWidget.ui'
#
# Created by: PyQt5 UI code generator 5.15.11
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_settingsUI(object):
    def setupUi(self, settingsUI):
        settingsUI.setObjectName("settingsUI")
        settingsUI.resize(718, 486)
        self.settingsUIWidget = QtWidgets.QWidget(settingsUI)
        self.settingsUIWidget.setGeometry(QtCore.QRect(0, 0, 601, 411))
        self.settingsUIWidget.setObjectName("settingsUIWidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.settingsUIWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setSpacing(11)
        self.gridLayout.setObjectName("gridLayout")
        self.startingPIn = QtWidgets.QLineEdit(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.startingPIn.setFont(font)
        self.startingPIn.setObjectName("startingPIn")
        self.gridLayout.addWidget(self.startingPIn, 3, 3, 1, 1)
        self.subsetSizeIn = QtWidgets.QLineEdit(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.subsetSizeIn.setFont(font)
        self.subsetSizeIn.setObjectName("subsetSizeIn")
        self.gridLayout.addWidget(self.subsetSizeIn, 2, 1, 1, 1)
        self.stepSizeLab = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.stepSizeLab.setFont(font)
        self.stepSizeLab.setObjectName("stepSizeLab")
        self.gridLayout.addWidget(self.stepSizeLab, 3, 0, 1, 1)
        self.label_9 = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.label_9.setFont(font)
        self.label_9.setObjectName("label_9")
        self.gridLayout.addWidget(self.label_9, 3, 2, 1, 1)
        self.refStartLab = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.refStartLab.setFont(font)
        self.refStartLab.setObjectName("refStartLab")
        self.gridLayout.addWidget(self.refStartLab, 4, 0, 1, 1)
        self.subsetSizeLab = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.subsetSizeLab.setFont(font)
        self.subsetSizeLab.setObjectName("subsetSizeLab")
        self.gridLayout.addWidget(self.subsetSizeLab, 2, 0, 1, 1)
        self.dicTypeBox = QtWidgets.QComboBox(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.dicTypeBox.setFont(font)
        self.dicTypeBox.setObjectName("dicTypeBox")
        self.dicTypeBox.addItem("")
        self.gridLayout.addWidget(self.dicTypeBox, 0, 1, 1, 1)
        self.maxIterLab = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.maxIterLab.setFont(font)
        self.maxIterLab.setObjectName("maxIterLab")
        self.gridLayout.addWidget(self.maxIterLab, 1, 2, 1, 1)
        self.stepSizeIn = QtWidgets.QLineEdit(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.stepSizeIn.setFont(font)
        self.stepSizeIn.setObjectName("stepSizeIn")
        self.gridLayout.addWidget(self.stepSizeIn, 3, 1, 1, 1)
        self.refBox = QtWidgets.QComboBox(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.refBox.setFont(font)
        self.refBox.setObjectName("refBox")
        self.gridLayout.addWidget(self.refBox, 4, 1, 1, 1)
        self.maxItIn = QtWidgets.QLineEdit(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.maxItIn.setFont(font)
        self.maxItIn.setObjectName("maxItIn")
        self.gridLayout.addWidget(self.maxItIn, 1, 3, 1, 1)
        self.convergenceIn = QtWidgets.QLineEdit(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.convergenceIn.setFont(font)
        self.convergenceIn.setObjectName("convergenceIn")
        self.gridLayout.addWidget(self.convergenceIn, 2, 3, 1, 1)
        self.shapeFuncLab = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.shapeFuncLab.setFont(font)
        self.shapeFuncLab.setObjectName("shapeFuncLab")
        self.gridLayout.addWidget(self.shapeFuncLab, 1, 0, 1, 1)
        self.dicTypeLab = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.dicTypeLab.setFont(font)
        self.dicTypeLab.setObjectName("dicTypeLab")
        self.gridLayout.addWidget(self.dicTypeLab, 0, 0, 1, 1)
        self.algoTypeBox = QtWidgets.QComboBox(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.algoTypeBox.setFont(font)
        self.algoTypeBox.setObjectName("algoTypeBox")
        self.gridLayout.addWidget(self.algoTypeBox, 0, 3, 1, 1)
        self.converLab = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.converLab.setFont(font)
        self.converLab.setObjectName("converLab")
        self.gridLayout.addWidget(self.converLab, 2, 2, 1, 1)
        self.shapeFuncBox = QtWidgets.QComboBox(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.shapeFuncBox.setFont(font)
        self.shapeFuncBox.setObjectName("shapeFuncBox")
        self.shapeFuncBox.addItem("")
        self.shapeFuncBox.addItem("")
        self.gridLayout.addWidget(self.shapeFuncBox, 1, 1, 1, 1)
        self.algorLab = QtWidgets.QLabel(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.algorLab.setFont(font)
        self.algorLab.setObjectName("algorLab")
        self.gridLayout.addWidget(self.algorLab, 0, 2, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)
        self.defaultsPBut = QtWidgets.QPushButton(self.settingsUIWidget)
        font = QtGui.QFont()
        font.setFamily("Figtree Light")
        font.setPointSize(11)
        self.defaultsPBut.setFont(font)
        self.defaultsPBut.setObjectName("defaultsPBut")
        self.verticalLayout.addWidget(self.defaultsPBut)

        self.retranslateUi(settingsUI)
        QtCore.QMetaObject.connectSlotsByName(settingsUI)

    def retranslateUi(self, settingsUI):
        _translate = QtCore.QCoreApplication.translate
        settingsUI.setWindowTitle(_translate("settingsUI", "Settings"))
        self.stepSizeLab.setText(_translate("settingsUI", "Step Size"))
        self.label_9.setText(_translate("settingsUI", "Starting Point"))
        self.refStartLab.setText(_translate("settingsUI", "Reference Start"))
        self.subsetSizeLab.setText(_translate("settingsUI", "Subset Size"))
        self.dicTypeBox.setItemText(0, _translate("settingsUI", "Planar"))
        self.maxIterLab.setText(_translate("settingsUI", "Max Iterations"))
        self.shapeFuncLab.setText(_translate("settingsUI", "Shape Function"))
        self.dicTypeLab.setText(_translate("settingsUI", "DIC Type"))
        self.converLab.setText(_translate("settingsUI", "Convergence"))
        self.shapeFuncBox.setItemText(0, _translate("settingsUI", "Linear"))
        self.shapeFuncBox.setItemText(1, _translate("settingsUI", "Quadratic"))
        self.algorLab.setText(_translate("settingsUI", "Algorythim"))
        self.defaultsPBut.setText(_translate("settingsUI", "Defaults"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    settingsUI = QtWidgets.QWidget()
    ui = Ui_settingsUI()
    ui.setupUi(settingsUI)
    settingsUI.show()
    sys.exit(app.exec_())
