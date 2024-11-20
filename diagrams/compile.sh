#!/bin/bash

for i in *.mmd; do
    mmdc -i $i -o ${i}.pdf -f
done

