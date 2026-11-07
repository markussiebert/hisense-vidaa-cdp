# Third-party notices

This project adapts ideas and a small amount of code from other open-source
projects. Their licenses and copyright notices are reproduced below.

## chrisns/hisense_vidaa

Portions of `custom_components/hisense_vidaa_cdp/cdp.py` are adapted from
[chrisns/hisense_vidaa](https://github.com/chrisns/hisense_vidaa):

- the single-persistent-WebSocket connection approach, including the finding
  that the TV's Chromium allows only one debugger client per page and that a
  connect/close cycle per call eventually strands a session until the TV is
  mains power-cycled;
- the `parse_inputs()` decode of the flat 6-tuple array returned by
  `model.source.getInputName()`.

That project is licensed under the MIT License:

```
MIT License

Copyright (c) 2026 Chris Nesbitt-Smith

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
