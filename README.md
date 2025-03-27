# MySmartWindow
MySmartWindow is a mobile app that let you manage the devices of your windows, and now, is a integration for Home Assistant, Where the user have the same functionality that he has on the app.

With this integration, you can control and manage your sensors, blinds, leds... 
Furthemore, you have the options to do custom automations.

# Integration MySmartWindow
Documentation about the devices available in the MySmartWindow APP. 

Although, if the user want some information about how to add this integration, we could provide it, There are some steps that you have to follow to add it:

1. From this link: https://www.mysmartwindow.com:22230/training/index.html, you need to be register as developer and using the validation code from the app MySmartWindow (it gets from the integrations option), you are going to get your Access Token.
2. Get the add-on From HACS using (⋮) > Custom Repositories, then, choose in "Category" the option Integration and add this link: "https://github.com/IoTFenster/MySmartWindow"
3. Go to services and devices.
4. Click on Add integration and search MySmartWindow, then you are going to introduce your access token.
5. Eventually, you are ready to use your devices from the App on Home Assistant.

# Requirements
The connection is socket, Therefore, to use this integration, you have to have the devices and home assistant at the same network, subnets are allowed. 

![](https://github.com/IoTFenster/MySmartWindow/blob/ae4087c2d41e5f162bde280304db29fb73a76745/custom_components/mysmartwindow/icon.png)
