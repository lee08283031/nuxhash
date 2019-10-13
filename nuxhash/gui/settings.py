from copy import deepcopy
from functools import wraps

import wx
from wx.lib.pubsub import pub
from wx.lib.agw.hyperlink import HyperLinkCtrl

from nuxhash import settings
from nuxhash.bitcoin import check_bc
from nuxhash.gui import main
from nuxhash.settings import DEFAULT_SETTINGS


REGIONS = ['eu', 'usa', 'jp', 'hk']
UNITS = ['BTC', 'mBTC']
INVALID_COLOR = 'PINK'


class SettingsScreen(wx.Panel):

    def __init__(self, parent, *args, frame=None, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self._Settings = None
        self._NewSettings = None
        pub.subscribe(self._OnSettings, 'data.settings')

        sizer = wx.BoxSizer(orient=wx.VERTICAL)
        self.SetSizer(sizer)

        def add_divider(sizer):
            sizer.Add(wx.StaticLine(self), wx.SizerFlags().Expand())

        def add_valign(sizer, window, sizerflags=wx.SizerFlags()):
            sizer.Add(window, sizerflags.Align(wx.ALIGN_CENTER_VERTICAL))

        def two_col_sizer(rows):
            sizer = wx.FlexGridSizer(rows, 2, main.PADDING_PX, main.PADDING_PX)
            sizer.AddGrowableCol(1)
            return sizer

        # Add basic setting controls.
        basicForm = wx.Window(self)
        sizer.Add(basicForm, wx.SizerFlags().Border(wx.ALL, main.PADDING_PX)
                                            .Expand())
        basicSizer = two_col_sizer(3)
        basicForm.SetSizer(basicSizer)

        add_valign(basicSizer, wx.StaticText(basicForm, label='Wallet address'))
        self._Wallet = AddressCtrl(basicForm, size=(-1, -1))
        self.Bind(wx.EVT_TEXT, self.OnWalletChange, self._Wallet)
        add_valign(basicSizer, self._Wallet, wx.SizerFlags().Expand())

        add_valign(basicSizer, wx.StaticText(basicForm, label='Worker name'))
        self._Worker = wx.TextCtrl(basicForm, size=(200, -1))
        self.Bind(wx.EVT_TEXT, self.OnWorkerChange, self._Worker)
        add_valign(basicSizer, self._Worker)

        add_valign(basicSizer, wx.StaticText(basicForm, label='Region'))
        self._Region = ChoiceByValue(
            basicForm, choices=REGIONS,
            fallbackChoice=settings.DEFAULT_SETTINGS['nicehash']['region'])
        self.Bind(wx.EVT_CHOICE, self.OnRegionChange, self._Region)
        add_valign(basicSizer, self._Region)

        # Add API key controls.
        apiCollapsible = wx.CollapsiblePane(
                self, label='API Keys', style=wx.CP_NO_TLW_RESIZE)
        self.Bind(
                wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnPaneChanged, apiCollapsible)
        sizer.Add(apiCollapsible, wx.SizerFlags().Border(wx.ALL, main.PADDING_PX)
                                                 .Expand())
        apiPane = apiCollapsible.GetPane()
        apiPaneSizer = wx.BoxSizer(orient=wx.VERTICAL)
        apiPane.SetSizer(apiPaneSizer)
        apiForm = wx.Window(apiPane)
        apiPaneSizer.Add(apiForm, wx.SizerFlags().Expand())
        apiFormSizer = two_col_sizer(3)
        apiForm.SetSizer(apiFormSizer)

        add_valign(apiFormSizer, wx.StaticText(apiForm, label='Organization ID'))
        self._Organization = wx.TextCtrl(apiForm, size=(-1, -1))
        add_valign(apiFormSizer, self._Organization, wx.SizerFlags().Expand())

        add_valign(apiFormSizer, wx.StaticText(apiForm, label='API Key Code'))
        self._ApiKey = wx.TextCtrl(
                apiForm, size=(-1, -1), style=wx.TE_PASSWORD)
        add_valign(apiFormSizer, self._ApiKey, wx.SizerFlags().Expand())

        add_valign(apiFormSizer,
                   wx.StaticText(apiForm, label='API Secret Key Code'))
        self._ApiSecret = wx.TextCtrl(
                apiForm, size=(-1, -1), style=wx.TE_PASSWORD)
        add_valign(apiFormSizer, self._ApiSecret, wx.SizerFlags().Expand())

        apiPaneSizer.AddSpacer(main.PADDING_PX)

        apiLink = HyperLinkCtrl(
                apiPane, label='(Get keys here)',
                URL='https://www.nicehash.com/my/settings/keys')
        apiPaneSizer.Add(apiLink, wx.SizerFlags().Expand())

        add_divider(sizer)

        # Add advanced setting controls.
        advancedForm = wx.Window(self)
        sizer.Add(advancedForm, wx.SizerFlags().Border(wx.ALL, main.PADDING_PX)
                                               .Expand())
        advancedSizer = two_col_sizer(3)
        advancedForm.SetSizer(advancedSizer)

        add_valign(advancedSizer,
                   wx.StaticText(advancedForm, label='Update interval (secs)'))
        self._Interval = wx.SpinCtrl(advancedForm, size=(125, -1),
                                     min=10, max=300, initial=60)
        self.Bind(wx.EVT_SPINCTRL, self.OnIntervalChange, self._Interval)
        add_valign(advancedSizer, self._Interval)

        add_valign(advancedSizer,
                   wx.StaticText(advancedForm,
                                 label='Profitability switch threshold (%)'))
        self._Threshold = wx.SpinCtrl(advancedForm, size=(125, -1),
                                      min=1, max=50, initial=10)
        self.Bind(wx.EVT_SPINCTRL, self.OnThresholdChange, self._Threshold)
        add_valign(advancedSizer, self._Threshold)

        add_valign(advancedSizer,
                   wx.StaticText(advancedForm, label='Display units'))
        self._Units = ChoiceByValue(
            advancedForm, choices=UNITS,
            fallbackChoice=settings.DEFAULT_SETTINGS['gui']['units'])
        self.Bind(wx.EVT_CHOICE, self.OnUnitsChange, self._Units)
        add_valign(advancedSizer, self._Units)

        sizer.AddStretchSpacer()

        # Add revert/save controls.
        saveForm = wx.Window(self)
        sizer.Add(saveForm, wx.SizerFlags().Border(wx.ALL, main.PADDING_PX)
                                           .Right())
        saveSizer = wx.BoxSizer(orient=wx.HORIZONTAL)
        saveForm.SetSizer(saveSizer)

        self._Revert = wx.Button(saveForm, id=wx.ID_REVERT_TO_SAVED)
        self.Bind(wx.EVT_BUTTON, self.OnRevert, self._Revert)
        saveSizer.Add(self._Revert)

        saveSizer.AddSpacer(main.PADDING_PX)

        self._Save = wx.Button(saveForm, id=wx.ID_APPLY)
        self.Bind(wx.EVT_BUTTON, self.OnSave, self._Save)
        saveSizer.Add(self._Save)

    def _OnSettings(self, settings):
        if settings != self._Settings:
            self._Settings = settings
            self._Reset()

    def _ChangeEvent(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            self._Revert.Enable()
            self._Save.Enable()
            method(self, *args, **kwargs)
        return wrapper

    @_ChangeEvent
    def OnWalletChange(self, event):
        self._NewSettings['nicehash']['wallet'] = event.GetString()

    @_ChangeEvent
    def OnWorkerChange(self, event):
        self._NewSettings['nicehash']['workername'] = event.GetString()

    @_ChangeEvent
    def OnRegionChange(self, event):
        self._NewSettings['nicehash']['region'] = REGIONS[event.GetSelection()]

    @_ChangeEvent
    def OnIntervalChange(self, event):
        self._NewSettings['switching']['interval'] = event.GetPosition()

    @_ChangeEvent
    def OnThresholdChange(self, event):
        self._NewSettings['switching']['threshold'] = event.GetPosition()/100.0

    @_ChangeEvent
    def OnUnitsChange(self, event):
        self._NewSettings['gui']['units'] = UNITS[event.GetSelection()]

    def OnPaneChanged(self, event):
        self.Layout()

    def OnRevert(self, event):
        self._Reset()

    def OnSave(self, event):
        pub.sendMessage('data.settings', settings=deepcopy(self._NewSettings))
        self._Revert.Disable()
        self._Save.Disable()

    def _Reset(self):
        self._NewSettings = deepcopy(self._Settings)

        self._Wallet.SetValue(self._Settings['nicehash']['wallet'])
        self._Worker.SetValue(self._Settings['nicehash']['workername'])
        self._Region.SetValue(self._Settings['nicehash']['region'])
        self._Interval.SetValue(self._Settings['switching']['interval'])
        self._Threshold.SetValue(self._Settings['switching']['threshold']*100)
        self._Units.SetValue(self._Settings['gui']['units'])
        self._Revert.Disable()
        self._Save.Disable()


class ChoiceByValue(wx.Choice):

    def __init__(self, *args, choices=[], fallbackChoice='', **kwargs):
        wx.Choice.__init__(self, *args, choices=choices, **kwargs)
        self._Choices = choices
        self._Fallback = fallbackChoice

    def SetValue(self, value):
        if value in self._Choices:
            wx.Choice.SetSelection(self, self._Choices.index(value))
        else:
            wx.Choice.SetSelection(self, self._Choices.index(self._Fallback))


class AddressCtrl(wx.TextCtrl):

    def __init__(self, parent, *args, **kwargs):
        wx.StaticText.__init__(self, parent, *args, **kwargs)
        self.Bind(wx.EVT_TEXT, self._OnSetValue)

    def _OnSetValue(self, event):
        if not check_bc(self.GetValue()):
            self.SetBackgroundColour(INVALID_COLOR)
        else:
            self.SetBackgroundColour(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
        event.Skip()

