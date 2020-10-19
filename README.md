## Summary
A python 3 script designed to work with the RaspberryPi, Enviro + Air Quality Hat, and Particulate Matter Sensor

## Materials
* I used a [Raspberry Pi Zero W](https://www.raspberrypi.org/products/raspberry-pi-zero-w/).  If you'd prefer not to solder the header use the [Raspberry Pi Zero WH](https://www.adafruit.com/product/3708).  Any Pi with a 40-pin male GPIO header should work fine.
* A microSD card with [Raspberry Pi OS](https://www.raspberrypi.org/downloads/).
* [Enviro + Air Quality for Raspberry Pi](https://shop.pimoroni.com/products/enviro?variant=3115568457171)
* [PMS5003 Particulate Matter Sensor](https://shop.pimoroni.com/products/pms5003-particulate-matter-sensor-with-cable)

## Software
I'm using [Python 3.7.3](https://www.python.org/downloads/release/python-373/).  After setting up the hardware I installed the [Python packages supplied by Pimoroni](https://github.com/pimoroni/enviroplus-python).  They supply a one-line installer but I didn't use it.  I did the following:
```
git clone https://github.com/pimoroni/enviroplus-python
cd enviroplus-python
sudo ./install.sh
```
I also had to install some packages manually.  I don't remember exactly which were installed manually but here's a summary of what I used:
* `ST7735` (for writing on the LCD screen)
* `psutil` (for accessing memory and CPU load)
* `gpiozero` (for accessing CPU temperature)
* `smbus2` and `bme280` (for reading the humidity and pressure sensors)
* `enviroplus` (for reading the gas sensor)
* `pms5003` (for reading the air quality sensors)

## Usage
Once everything is set up just run the script:
```
python3 runEnviroPi.py
```
I used the following cron job to schedule the script to run when the Pi boots:
```
@reboot Python3 /home/pi/EnviroPi/runEnviroPi.py
```

## References
* [An outdoor air quality station with Enviro+ and Luftdaten](https://learn.pimoroni.com/tutorial/sandyj/enviro-plus-luftdaten-air-quality-station):  A guide written by [Sandy Macdonald](https://sandyjmacdonald.github.io) (hosted on [Pimoroni](https://learn.pimoroni.com)) discussing how to set up and use the hardware.
* [enviroplus-python](https://github.com/pimoroni/enviroplus-python):  The github repository contains many helpful examples.