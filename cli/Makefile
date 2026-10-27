CC=gcc
CFLAGS=-O2 -Wall -Wextra

all: alg-rgb alg-fan

alg-rgb: alg-rgb.c
	$(CC) $(CFLAGS) alg-rgb.c -o alg-rgb

alg-fan: alg-fan.c
	$(CC) $(CFLAGS) alg-fan.c -o alg-fan

clean:
	rm -f alg-rgb alg-fan
