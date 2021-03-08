"""
Perfusion simulation Quantiphyse plugin

GUIs for structural models, i.e. QtWidget instances which control the options
of a structural model

Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

from __future__ import division, unicode_literals, absolute_import, print_function

import time

import numpy as np

try:
    from PySide import QtGui, QtCore, QtGui as QtWidgets
except ImportError:
    from PySide2 import QtGui, QtCore, QtWidgets

from quantiphyse.data import NumpyData, DataGrid, ImageVolumeManagement
from quantiphyse.gui.options import OptionBox, DataOption, NumericOption, BoolOption, NumberListOption, TextOption, ChoiceOption, RunButton
from quantiphyse.utils import QpException, get_plugins
from quantiphyse.processes import Process

from .struc_models import *

class AddEmbeddingDialog(QtGui.QDialog):
    """
    Dialog box enabling one item to be chosen from a list
    """

    def __init__(self, parent, ivm, existing_strucs):
        super(AddEmbeddingDialog, self).__init__(parent)
        self.ivm = ivm
        self.sel_text = None
        self.sel_data = None
        self.existing_names = [struc.name for struc in existing_strucs]

        self.setWindowTitle("Add embedding")
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self._opts = OptionBox()
        pvmap = self._opts.add("PV map / mask", DataOption(ivm, data=True, rois=True), key="pvmap")
        pvmap.sig_changed.connect(self._pvmap_changed)
        name = self._opts.add("Name of embedded structure", TextOption(), key="name")
        name.textChanged.connect(self._name_changed)
        self._opts.add("Structure type", ChoiceOption(["Embedding", "Activation mask", "Additional PVE"], return_values=["embed", "act", "add"]), key="type")
        self._opts.add("Parent structure", ChoiceOption([s.display_name for s in existing_strucs], [s.name for s in existing_strucs]), key="parent")
        vbox.addWidget(self._opts)

        self.button_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
        vbox.addWidget(self.button_box)

    def _pvmap_changed(self):
        if self.name == "" and self.pvmap:
            qpdata = self.ivm.data[self.pvmap]
            self._opts.option("name").value = qpdata.name

    def _name_changed(self):
        accept = self.name != "" and self.name not in self.existing_names
        self.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(accept)

    @property
    def pvmap(self):
        return self._opts.option("pvmap").value

    @property
    def name(self):
        return self._opts.option("name").value

    @property
    def struc_type(self):
        return self._opts.option("type").value

    @property
    def parent_struc(self):
        return self._opts.option("parent").value

class UserPvModelView:
    """
    View for UserPvModel - a structural model where user supplies partial volume maps
    """

    def __init__(self, ivm):
        self.model = UserPvModel(ivm)
        self.model.options.update({
            "pvmaps" : {},
            "additional" : {},
        })
        self.gui = OptionBox()
        self.gui.sig_changed.connect(self._update_options)
        self._refresh_gui()

    def _refresh_gui(self):
        options = self.model.options
        self.gui.clear()
        for struc in self.model.default_strucs:
            data_opt = self.gui.add("%s map" % struc.name.upper(), DataOption(self.model._ivm, explicit=True), checked=True, enabled=struc.name in options["pvmaps"], key=struc.name)
            data_opt.value = options["pvmaps"].get(struc.name, None)
        for struc in options["additional"].values():
            del_btn = self._struc_delete_btn(struc)
            display_type = {"add" : "map", "embed" : "embedding", "act" : "mask"}.get(struc["struc_type"], "map")
            data_opt = self.gui.add("%s %s" % (struc["name"], display_type), DataOption(self.model._ivm, explicit=True, rois=True), del_btn, key=struc["name"])
            data_opt.value = struc.get("pvmap", None)
        self.gui.add(None, RunButton("Add user-defined structure", callback=self._add_embedding), key="add_embedding")

    def _update_options(self):
        self.model.options["pvmaps"] = self.gui.values()

    def _struc_delete_btn(self, add_struc):
        def _del_cb():
            self._del_struc(add_struc["name"])

        btn = QtGui.QPushButton("Delete")
        btn.clicked.connect(_del_cb)
        return btn

    def _del_struc(self, name):
        self.model.options["additional"].pop(name, None)
        self._refresh_gui()

    def _add_embedding(self):
        dialog = AddEmbeddingDialog(self.gui, self.model._ivm, self.model.default_strucs)
        try:
            accept = dialog.exec_()
        except:
            import traceback
            traceback.print_exc()
        if accept:
            self.model.options["additional"][dialog.name] = {"name" : dialog.name, "struc_type" : dialog.struc_type, "parent_struc" : dialog.parent_struc, "pvmap" : dialog.pvmap}
            self._refresh_gui()

class FastStructureModelView:
    """
    View for FastStructureModel
    """
    def __init__(self, ivm):
        self.model = FastStructureModel(ivm)
        self.gui = OptionBox()
        self.gui.add("Structural image (brain extracted)", DataOption(self.model._ivm, explicit=True), key="struc")
        self.gui.add("Image type", ChoiceOption(["T1 weighted", "T2 weighted", "Proton Density"], return_values=[1, 2, 3]), key="type")
        self.gui.sig_changed.connect(self._update_options)
        
    def _update_options(self):
        self.model.options.update(self.gui.values())

class CheckerboardModelView:
    """
    View for CheckerboardModel
    """
    def __init__(self, ivm):
        self.model = CheckerboardModel(ivm)
        self.gui = OptionBox()
        self.gui.add("Number of voxels per patch (approx)", NumericOption(minval=1, maxval=1000, default=20, intonly=True), key="voxels-per-patch")
        self.gui.sig_changed.connect(self._update_options)
        
    def _update_options(self):
        self.model.options.update(self.gui.values())
