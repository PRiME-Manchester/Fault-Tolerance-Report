# The name of the binary to be built 
APP = reinjector

APP_OUTPUT_DIR = ../../network_tester/binaries/
BUILD_DIR = build/

OBJECTS = reinjector.o
#LIBRARIES = -lspin1_api

include $(SPINN_DIRS)/Makefile.common

all: $(APP_OUTPUT_DIR)$(APP).aplx

clean:
	$(RM) $(OBJECTS) $(BUILD_DIR)$(APP).elf $(BUILD_DIR)$(APP).txt $(APP_OUTPUT_DIR)$(APP).aplx
