import machine
import os
from config import SD_SPI_ID, SD_PIN_SCK, SD_PIN_MOSI, SD_PIN_MISO, SD_CS, SD_POWER

print("Enabling SD power...")
pwr = machine.Pin(SD_POWER, machine.Pin.OUT)
pwr.value(1)

print("Initializing SPI for SD...")

spi = machine.SPI(
    SD_SPI_ID,
    baudrate=1_000_000,
    polarity=0,
    phase=0,
    sck=machine.Pin(SD_PIN_SCK),
    mosi=machine.Pin(SD_PIN_MOSI),
    miso=machine.Pin(SD_PIN_MISO),
)

cs = machine.Pin(SD_CS, machine.Pin.OUT)
cs.value(1)

print("Creating SDCard object...")
sd = machine.SDCard(spi=spi, cs=cs)

print("Formatting SD card to FAT...")
vfs = os.VfsFat(sd)
os.mount(vfs, "/sd")

print("Formatting complete.")
print("Listing /sd:")
print(os.listdir("/sd"))