import sys
import time
from datetime import datetime, timedelta
import math
from PIL import Image, ImageDraw, ImageFont
from fonts.ttf import RobotoMedium as UserFont
# used to communicate with Adafruit IO.
from Adafruit_IO import Client, Feed, Data, RequestError
# used to draw on the LCD
import ST7735
# used for Memory and CPU load
import psutil
# used for CPU temp
from gpiozero import CPUTemperature
# used for humidity and pressure
from smbus2 import SMBus
from bme280 import BME280
# used for gasses
from enviroplus import gas
# used for pollution
from pms5003 import PMS5003, ReadTimeoutError as pmsReadTimeoutError
# used for light and proximity
from ltr559 import LTR559

# Change this to false if you decide not to use AIO.
USE_AIO = True
# Initializing the Adafruit IO feeds
aio = ""
if USE_AIO:
    try:
        aioCredentials = open("AdafruitUserInfo", "r")
        aioName = aioCredentials.readline().rstrip('\n')
        aioKey  = aioCredentials.readline().rstrip('\n')
        aioCredentials.close()
        aio = Client(aioName, aioKey)
    except FileNotFoundError:
        USE_AIO = False
# This function will be used repeatedly to get feed keys from the client or create a new one.
def initializeFeed(client, feedKey):
    returnKey = ""
    if USE_AIO:
        try:
            feed = client.feeds(feedKey.lower())
            returnKey = feed.key
        except RequestError:
            feed = Feed(name = feedKey.lower())
            feed = client.create_feed(feed)
            returnKey = feed.key
    return returnKey
# This function will be used to report data to AIO.
def reportToAIO(feedKey, value):
    if USE_AIO:
        aio.append(feedKey, value)
# Here is where we initialize the feeds that we use for reporting
aioKey_gasRed = initializeFeed(aio, "EnviroPi-GasReducing")
aioKey_gasOxi = initializeFeed(aio, "EnviroPi-GasOxidising")
aioKey_gasNH3 = initializeFeed(aio, "EnviroPi-GasNH3")
aioKey_polLar = initializeFeed(aio, "EnviroPi-PollutionLarge")
aioKey_polMed = initializeFeed(aio, "EnviroPi-PollutionMedium")
aioKey_polSml = initializeFeed(aio, "EnviroPi-PollutionSmall")
aioKey_humidity = initializeFeed(aio, "EnviroPi-Humidity")
aioKey_pressure = initializeFeed(aio, "EnviroPi-Pressure")
aioKey_light = initializeFeed(aio, "EnviroPi-Light")
aioKey_proximity = initializeFeed(aio, "EnviroPi-Proximity")
# NOTE: There are some bad practices here.  Later in the script we'll call reportToAIO repeatedly so its
#       arguments must exist even if we're not using AIO.  So if the user decides not to use AIO or if the
#       credentials file is missing then the value of "aio" and the values of these keys are assigned to
#       be an empty string.  However, that will only happen if USE_AIO == False and so those variables will
#       never be used.  This is bad practice but for such a small script I didn't bother doing it right.

# Initializing the sensors
# The gas sensor doesn't need initialized like this.
BME280 = BME280(i2c_dev = SMBus(1))
PMS5003 = PMS5003()
LTR559 = LTR559()

# Initializing the LCD
DISPLAY = ST7735.ST7735(port = 0, cs = 1, dc = 9, backlight = 12, rotation = 90, spi_speed_hz = 10000000)

# Initializing the image to DISPLAY on the LCD
WIDTH = DISPLAY.width
HEIGHT = DISPLAY.height
IMG = Image.new('RGB', (WIDTH, HEIGHT), color = (0, 0, 0))
DRAW = ImageDraw.Draw(IMG)
BOXWIDTH_STATUS = 10
BOXWIDTH_AIO = 2

# Color variables
COLOR_BACKGROUND     = (0, 0, 0)
COLOR_TEXT_SAFE      = (255, 255, 255)
COLOR_TEXT_MILD      = (0, 255, 0)
COLOR_TEXT_MODERATE  = (255, 255, 0)
COLOR_TEXT_UNSAFE    = (255, 0, 0)
COLOR_AIO_IN_USE     = (0, 0, 255)
COLOR_AIO_FAIL       = (255, 255, 255)

# A global variable which represents a missing value.
MISSING_VALUE = -1

# Approximate delay between screen changes (seconds).
SCREEN_CHANGE_DELAY = 5

# Maximum length of arrays used for averaging.
MAX_ARRAY_LENGTH = 1000

# Warm up time before averaging starts.
WARMUP_TIME = timedelta(minutes = 2)

# Adafruit imposes a limit on the rate of uploads.  This variable sets the minimum time between uploads.
MIN_TIME_BETWEEN_AIO_REPORTS = timedelta(minutes = 2)

# A function to format the Air Quality strings.
def formatAirQualityText(prefix, level, avg):
    returnString = prefix + ":"
    if level != MISSING_VALUE:
        returnString = returnString + " " + str(round(level))
    if avg != MISSING_VALUE:
        returnString = returnString + " (" + str(round(avg)) + ")"
    return returnString

# Returns COLOR_TEXT_XXX based on comparing a number to 3 levels.
def getColorByLevel(level, lowThreshold, midThreshold, highThreshold):
    returnColor = COLOR_TEXT_SAFE
    if level >= highThreshold:
        returnColor = COLOR_TEXT_UNSAFE
    elif level >= midThreshold:
        returnColor = COLOR_TEXT_MODERATE
    elif level >= lowThreshold:
        returnColor = COLOR_TEXT_MILD
    return returnColor

# A function to get the appropriate color for the gas.
def getGasColor(level, avg):
    returnColor = COLOR_TEXT_SAFE
    if (level != MISSING_VALUE) and (avg != MISSING_VALUE):
        returnColor = getColorByLevel(level, avg, 1.5*level, 2*level)
    return returnColor

# A function to get the appropriate color for pollution.
def getPollutionColor(level):
    returnColor = COLOR_TEXT_SAFE
    if level != MISSING_VALUE:
        returnColor = getColorByLevel(level, 12, 35, 55)
    return returnColor

# A function to get the appropriate color for humidity.
def getHumidityColor(level):
    return getColorByLevel(level, 30, 50, 70)

# A function to get the appropriate color for pressure.
def getPressureColor(level):
    return getColorByLevel(1/level, 1/1000, 1/700, 1/400)

# A function to get the appropriate color for CPU temperature.
def getCPUTempColor(level):
    return getColorByLevel(level, 25, 50, 75)

# A function to get the appropriate color for CPU load.
def getCPULoadColor(level):
    return getColorByLevel(level, 25, 50, 75)

# A function to get the appropriate color for memory load.
def getMemLoadColor(level):
    return getColorByLevel(level, 25, 50, 75)

# A function to get the most severe color in a list of colors.
def getMaxColor(listOfColors):
    returnColor = COLOR_TEXT_SAFE
    if COLOR_TEXT_UNSAFE in listOfColors:
        returnColor = COLOR_TEXT_UNSAFE
    elif COLOR_TEXT_MODERATE in listOfColors:
        returnColor = COLOR_TEXT_MODERATE
    elif COLOR_TEXT_MILD in listOfColors:
        returnColor = COLOR_TEXT_MILD
    return returnColor

# A function to draw a list of strings with given colors on the LCD screen
def drawText(strings, colors):
    fontSize = math.floor(HEIGHT / len(strings))
    font = ImageFont.truetype(UserFont, fontSize)
    for i in range(0, max(len(strings), len(colors))):
        DRAW.text((BOXWIDTH_AIO+2, math.floor(i * HEIGHT / len(strings))), strings[i], font = font, fill = colors[i])

def drawAIOStatus(color):
    DRAW.rectangle((0, 0, BOXWIDTH_AIO, HEIGHT), color)

# This timestamp will be used to keep track of the uptime.
timeStart = datetime.now()

# This variable records the most recent AIO report to ensure that we don't write too often.
lastAIOReport = datetime.now()

# Initializing averaging arrays
listGasRed = []
listGasOxi = []
listGasNH3 = []
listPolLar = []
listPolMed = []
listPolSml = []

# Initializing variables used for the AIO warning box.
colAIO = COLOR_BACKGROUND

# The following infinite loop repeatedly polls the sensors for data and then writes the data to the LCD screen.
# It can be interrupted by a keyboard interrupt.
try:
    while True:
        uptime = datetime.now() - timeStart

        ###########################
        # First Screen: Air Quality
        ###########################

        # Getting the gas readings,
        
        gasReading = gas.read_all()
        gasRed = gasReading.reducing / 1000
        gasOxi = gasReading.oxidising / 1000
        gasNH3 = gasReading.nh3 / 1000
        listGasRed.append(gasRed)
        listGasOxi.append(gasOxi)
        listGasNH3.append(gasNH3)
        # Remove first item from lists if warmup isn't over or if there are more than the maximum elements.
        if (uptime < WARMUP_TIME) or (len(listGasRed) > MAX_ARRAY_LENGTH):
            listGasRed.pop(0)
            listGasOxi.pop(0)
            listGasNH3.pop(0)
        # If there are any items in the list then we use the list to find an average.
        if len(listGasRed) > 0:
            avgGasRed = sum(listGasRed) / len(listGasRed)
            avgGasOxi = sum(listGasOxi) / len(listGasOxi)
            avgGasNH3 = sum(listGasNH3) / len(listGasNH3)
        # Otherwise we use MISSING_VALUE for the average.
        else:
            avgGasRed = MISSING_VALUE
            avgGasOxi = MISSING_VALUE
            avgGasNH3 = MISSING_VALUE

        # Gathering the pollution readings.
        
        # We have to account for the fact that sometimes this read fails.
        try:
            polReading = PMS5003.read()
            polLar = polReading.pm_ug_per_m3(10)
            polMed = polReading.pm_ug_per_m3(2.5)
            polSml = polReading.pm_ug_per_m3(1)
        # If the read fails then we use MISSING_VALUE as placeholder values.
        except pmsReadTimeoutError:
            polLar = MISSING_VALUE
            polMed = MISSING_VALUE
            polSml = MISSING_VALUE
        # We only add values to the lists if the read actually succeeded.
        else:
            listPolLar.append(polLar)
            listPolMed.append(polMed)
            listPolSml.append(polSml)

        # Remove first item from lists if warmup isn't over or if there are more than the maximum elements.
        if (uptime < WARMUP_TIME) or (len(listPolLar) > MAX_ARRAY_LENGTH):
            # Since it's possible that pms5003.read() can fail we must also check that the lists have elements.
            if len(listPolLar) > 0:
                listPolLar.pop(0)
                listPolMed.pop(0)
                listPolSml.pop(0)
        # If there are any items in the list then we use the list to find an average.
        if len(listPolLar) > 0:
            avgPolLar = sum(listPolLar) / len(listPolLar)
            avgPolMed = sum(listPolMed) / len(listPolMed)
            avgPolSml = sum(listPolSml) / len(listPolSml)
        # Otherwise we use MISSING_VALUE for the average.
        else:
            avgPolLar = MISSING_VALUE
            avgPolMed = MISSING_VALUE
            avgPolSml = MISSING_VALUE

        # Getting things ready to print.

        # Making the strings that get printed.
        strGasRed = formatAirQualityText("GasRed", gasRed, avgGasRed)
        strGasOxi = formatAirQualityText("GasOxi", gasOxi, avgGasOxi)
        strGasNH3 = formatAirQualityText("GasHN3", gasNH3, avgGasNH3)
        strPolLar = formatAirQualityText("Dst/Pln/Mld", polLar, avgPolLar)
        strPolMed = formatAirQualityText("Smk/Org/Mtl", polMed, avgPolMed)
        strPolSml = formatAirQualityText("Ultrafine", polSml, avgPolSml)
        listOfStrings = [strGasRed, strGasOxi, strGasNH3, strPolLar, strPolMed, strPolSml]

        # Getting the colors for the strings.
        colGasRed = getGasColor(gasRed, avgGasRed)
        colGasOxi = getGasColor(gasOxi, avgGasOxi)
        colGasNH3 = getGasColor(gasNH3, avgGasNH3)
        colPolLar = getPollutionColor(polLar)
        colPolMed = getPollutionColor(polMed)
        colPolSml = getPollutionColor(polSml)
        listOfColors = [colGasRed, colGasOxi, colGasNH3, colPolLar, colPolMed, colPolSml]

        # Colors for the alert boxes.
        gasAlertColor = getMaxColor([colGasRed, colGasOxi, colGasNH3])
        polAlertColor = getMaxColor([colPolLar, colPolMed, colPolSml])

        # Drawing the screen
        DRAW.rectangle((0, 0, WIDTH, HEIGHT), COLOR_BACKGROUND)
        drawText(listOfStrings, listOfColors)
        DRAW.rectangle((WIDTH-BOXWIDTH_STATUS, 0, WIDTH, HEIGHT/2), gasAlertColor)
        DRAW.rectangle((WIDTH-BOXWIDTH_STATUS, HEIGHT/2, WIDTH, HEIGHT), polAlertColor)
        drawAIOStatus(colAIO)
        DISPLAY.display(IMG)

        # Display the Air Quality metrics for a while.
        time.sleep(SCREEN_CHANGE_DELAY)

        ##############################
        # Second Screen: Miscellaneous
        ##############################

        # Humidity reading as a percentage.
        humidity = BME280.get_humidity()
        strHumidity = "Humidity: " + str(round(humidity)) + "%"
        colHumidity = getHumidityColor(humidity)
        # Pressure reading in kPa.
        pressure = BME280.get_pressure()
        strPressure = "Pressure: " + str(round(pressure)) + "kPa"
        colPressure = COLOR_TEXT_UNSAFE
        if pressure > 0:
            colPressure = getPressureColor(pressure)
        # CPU temperature in degrees C.
        CPUTemp = CPUTemperature().temperature
        strCPUTemp = "CPU Temp: " + str(round(CPUTemp)) + "C"
        colCPUTemp = getCPUTempColor(CPUTemp)
        # CPU load as a percentage.
        CPULoad = psutil.cpu_percent()
        strCPULoad = "CPU Load: " + str(round(CPULoad)) + "%"
        colCPULoad = getCPULoadColor(CPULoad)
        # Memory Load as a percentage.
        memLoad = psutil.virtual_memory().percent
        strMemLoad = "Memory Load: " + str(round(memLoad)) + "%"
        colMemLoad = getMemLoadColor(memLoad)
        # Uptime as HH:MM:SS
        totalSeconds = round(uptime.total_seconds())
        hours, remainder = divmod(totalSeconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptimeFormatted = str(timedelta(hours = hours, minutes = minutes, seconds = seconds))
        strUptime = "Uptime: " + uptimeFormatted
        colUptime = COLOR_TEXT_SAFE

        # These are some other things that I'm reporting to AIO but don't display on the LCD.
        light = LTR559.get_lux()
        proximity = LTR559.get_lux()

        # List of strings and colors to be used for printing.
        listOfStrings = [strHumidity, strPressure, strCPUTemp, strCPULoad, strMemLoad, strUptime]
        listOfColors  = [colHumidity, colPressure, colCPUTemp, colCPULoad, colMemLoad, colUptime]

        # Drawing the screen
        DRAW.rectangle((0, 0, WIDTH, HEIGHT), COLOR_BACKGROUND)
        drawText(listOfStrings, listOfColors)
        drawAIOStatus(colAIO)
        DISPLAY.display(IMG)

        # Display the Miscellaneous values for a while.
        time.sleep(SCREEN_CHANGE_DELAY)

        ##################
        # Reporting to AIO
        ##################

        if USE_AIO and uptime > WARMUP_TIME and datetime.now() - lastAIOReport > MIN_TIME_BETWEEN_AIO_REPORTS:
            try:
                # Reporting harmful gasses.
                reportToAIO(aioKey_gasRed, gasRed)
                reportToAIO(aioKey_gasOxi, gasOxi)
                reportToAIO(aioKey_gasNH3, gasNH3)
                # Reporting pollution.
                reportToAIO(aioKey_polLar, polLar)
                reportToAIO(aioKey_polMed, polMed)
                reportToAIO(aioKey_polSml, polSml)
                # Reporting other sensors.
                reportToAIO(aioKey_humidity, humidity)
                reportToAIO(aioKey_pressure, pressure)
                reportToAIO(aioKey_light, light)
                # reportToAIO(aioKey_proximity, proximity)
                # Resetting the timestamp on the last AIO report.
                lastAIOReport = datetime.now()
                # Change the color of the indicator to show that the AIO report succeeded.
                colAIO = COLOR_AIO_IN_USE
            except:
                # This only happens if the AIO report fails for some reason.
                colAIO = COLOR_AIO_FAIL

except KeyboardInterrupt:
    DRAW.rectangle((0, 0, WIDTH, HEIGHT), COLOR_BACKGROUND)
    DISPLAY.display(IMG)
    DISPLAY.set_backlight(0)
