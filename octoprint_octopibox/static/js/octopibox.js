/*
 * View model for OctoPrint-OctoPiBox
 *
 * Author: S W Hillier
 * License: AGPLv3
 */
$(function(){
    function DisplayPowerViewModel(viewModels) {
        var self = this;
        self.printerStateViewModel = viewModels[0];
        self.printerStateViewModel.powerStatusText = ko.observable("-");

        self.onStartup = function() {
            var element = $("#state").find(".accordion-inner .progress");
            if (element.length) {
                var text = gettext("Printer Power");
                var tooltip = gettext("OctoPiBox printer power state.");
             	element.before(text + ": <strong id='powerStatus' title='" + tooltip + "' data-bind='text: powerStatusText'></strong><br>");
            }
        };

	self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "octopibox") {
                return;
            }
	    if (data.type == "updatePowerStatus") {
		self.printerStateViewModel.powerStatusText(data.power_status_value);
	    }
	}


    }

    OCTOPRINT_VIEWMODELS.push([
	DisplayPowerViewModel,
	"printerStateViewModel", []
    ]);
});


$(function(){
    function OctoPiBoxViewModel(parameters) {
        var self = this;

        // Hack to remove automatically added Cancel button
        // See https://github.com/sciactive/pnotify/issues/141
        PNotify.prototype.options.confirm.buttons = [];
        self.timeoutPopupText = gettext('Powering off in ');
        self.timeoutPopupOptions = {
            title: gettext('Automatic Printer Power-off'),
            type: 'notice',
            icon: true,
            hide: false,
            confirm: {
                confirm: true,
                buttons: [{
                    text: 'Abort Automatic Power-off',
                    addClass: 'btn-block btn-danger',
                    promptTrigger: true,
                    click: function(notice, value){
                        notice.remove();
                        notice.get().trigger("pnotify.cancel", [notice, value]);
                    }
                }]
            },
            buttons: {
                closer: false,
                sticker: false,
            },
            history: {
                history: false
            }
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "octopibox") {
                return;
            }
            if (data.type == "timeout") {
                if (data.timeout_value > 0) {
                    self.timeoutPopupOptions.text = self.timeoutPopupText + data.timeout_value;
                    if (self.timeoutPopup !== undefined) {
                        self.timeoutPopup.update(self.timeoutPopupOptions);
                    } else {
                        self.timeoutPopup = new PNotify(self.timeoutPopupOptions);
                        self.timeoutPopup.get().on('pnotify.cancel', function() {self.abortPrinterOff(true);});
                    }
                } else {
                    self.timeoutPopup.remove();
                    self.timeoutPopup = undefined;
                }
            } else if (data.type == "close_popup") {
                if (self.timeoutPopup !== undefined) {
                    self.timeoutPopup.remove();
                    self.timeoutPopup = undefined;
                }            
            }
        }

        self.abortPrinterOff = function(abortPrinterOffValue) {
            self.timeoutPopup.remove();
            self.timeoutPopup = undefined;
            $.ajax({
                url: API_BASEURL + "plugin/octopibox",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "abort"
                }),
                contentType: "application/json; charset=UTF-8"
            })
        }
    }

    OCTOPRINT_VIEWMODELS.push([
	OctoPiBoxViewModel,
/*        [], document.getElementById("settings_plugin_octopibox") */
        [], []
    ]);
});
