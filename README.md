# PDF-wordcount
A simple TUI tool to get you a wordcount in a PDF, allowing you to exclude/include sections.

### Installation
#### Pre-requisites
Using `pipx` to install. If you don't already have that:
`sudo apt install pipx` <br>
or on windows: <br>
`python -m pip install --user pipx` <br>
`python -m pipx ensurepath`<- restart terminal after this one

#### install pdfwc
`git clone https://github.com/jwhogg/pdfwc --depth=1` <br>
`pipx install ./pdfwc/pdfwc`

### Usage
`pdfwc my_pdf.pdf`
- press `space` to toggle the currently highlighed section in the wordcount calculation
- `a` to toggle all
- `q` to quit

<img width="1143" height="635" alt="image" src="https://github.com/user-attachments/assets/020b51f3-a8db-40f4-9004-0fedf9fa8329" />

#### Caveats
This program relies on `PyMuPDF`, so it will not work for pdfs that are pure images, and will struggle when the pdf has no outline / table of contents. Milage may vary.
