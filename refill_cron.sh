#!/bin/bash
cd /root/xlayer
python3 -c "
import refill, logging
logging.basicConfig(level=logging.WARNING)
refill.check_and_refill()
"
