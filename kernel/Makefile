obj-m += alg_rgb.o

ccflags-y += -I$(src)/../include

KDIR ?= /lib/modules/$(if $(KERNELRELEASE),$(KERNELRELEASE),$(shell uname -r))/build
PWD  := $(shell pwd)

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
