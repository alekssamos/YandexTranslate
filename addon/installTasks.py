import config
import addonHandler
import gui
import wx

addonHandler.initTranslation()


def onInstall():
	if "YandexTranslate" not in config.conf: config.conf["YandexTranslate"]={}
	config.conf["YandexTranslate"]["api"] = "broker1"
	config.conf["YandexTranslate"]["useProxy"] = False
	gui.messageBox(_("Many users reported problems with the service when others were doing well. I have added a new API type to the settings of this add-on. All requests to Yandex will go through my own server. You can disable this by still selecting the web or iOS API in the add-on settings. I will collect and analyze your requests to track and fix errors."), _("Yandex Translate"), style=wx.OK | wx.ICON_WARNING)
