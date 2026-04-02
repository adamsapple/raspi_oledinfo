import gzip
from PIL import ImageFont
from PIL import BdfFontFile
from PIL import PcfFontFile

FONT_SIZE = 14

#with open(f"/usr/share/fonts/X11/misc/ter-u{FONT_SIZE}n.bdf", "rb") as fp:
#    font = BdfFontFile.BdfFontFile(fp)
#    font.save("fonts/ter-u{FONT_SIZE}n")   # fonts/ter-u14n.pil と companion bitmap を作る

with gzip.open(f"/usr/share/fonts/X11/misc/ter-u{FONT_SIZE}n_iso-8859-1.pcf.gz", "rb") as fp:
    font = PcfFontFile.PcfFontFile(fp)
    font.save(f"fonts/ter-u{FONT_SIZE}n.pil")   # fonts/ter-u14n.pil と companion bitmap を作る