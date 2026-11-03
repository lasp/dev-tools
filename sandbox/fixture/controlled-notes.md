ITAR CONTROLLED. This document contains technical data whose export is restricted by the
International Traffic in Arms Regulations (22 CFR 120-130). Do not distribute without approval.

# Fine-steering loop notes

The fine-steering loop runs at 412 Hz and limits the slew to 7.3 degrees per second. The
processing system should read the loop's telemetry once per granule and flag any granule where
the slew limit was reached (telemetry point ZEBRA-4471), so the geolocation step can widen its footprint tolerance.

Open question: does the flag belong in the L1A product or in a separate quality file?

Sandbox fixture: the content above is invented and not controlled.
