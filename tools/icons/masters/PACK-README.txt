Tracks and Trails
Logo Asset Package
Version 1.1 · Released 2026-08-25 · Supersedes 1.0



WHAT CHANGED IN 1.1
Adds the Icon cut: the Standard artwork with the sound waves removed, for square tiles — desktop, dock and
launcher icons — where the waves push the mark off-centre in the frame and read as a stray flick. Geometry
is otherwise identical to Standard, so the cuts share stem weight, trail and baseline exactly.
The Icon cut ships eleven SVG colourways, ten vector PDFs, forty PNG exports and a four-colourway
app-icon set. The three-cut comparison sheet Cuts.png replaces Standard-vs-Small.png, and both overview
sheets are re-rendered to carry the new version number. No existing artwork changed.


THE THREE CUTS
Cut                          Artwork bounds                       Use
Standard                     918 × 1072 units                     48 px wide and above
Icon                         842 × 1072 units                     Square tiles, 48 px and above
Small                        828 × 1072 units                     Below 48 px wide

Standard carries every feature: three trees, mountain, trail and sound waves. Icon removes only the sound
waves. Small removes the trees, mountain and waves.
The 48 px breakpoint is measured, not conventional: below it the third tree and the mountain notch stop
resolving. The Icon cut keeps every one of those features, so it shares Standard's 48 px floor rather than
earning a lower one. Below 48 px, use Small.
The three cuts are different shapes and must not be scaled interchangeably within one layout. Pick one per
context.


BACKGROUND USAGE
OnLight files are drawn for light backgrounds; OnDark for dark ones. Mono-Black and Mono-White name their
ink, and are chosen to contrast with the ground they sit on.


COLOURWAYS AND COLOUR VALUES
Colourway                        Mass tone              Accent
Brand-OnLight                    #1E5E47                #D9A24C
Brand-OnDark                     #48906C                #D9A24C
Amber-OnLight                    #7A4200                #FA9313
Amber-OnDark                     #B86B0B                #FFB960
Evergreen-OnLight                #095436                #55B486
Evergreen-OnDark                 #368861                #8FDBB2
Ink-OnLight                      #111111                #636363
Ink-OnDark                        #FFFFFF                 #919191
Mono-Black                        #111111                 #111111
Mono-White                        #FFFFFF                 #FFFFFF
Mono-CurrentColor                 currentColor            currentColor

All three cuts of a colourway carry these values exactly. Colourway names are permanent across package
revisions.


COLOUR SYSTEMS
RGB / hex only. CMYK, Pantone and spot equivalents have not been defined for this identity. Do not convert
on the brand's behalf — an unapproved conversion is a change to the brand colours. Request approved
values before a print or signage run.


MONO-CURRENTCOLOR — READ BEFORE USE
This file has no fixed colour. Inlined into HTML it inherits the surrounding text colour; referenced through an
img tag, or opened in a design tool, it renders black. It therefore ships as SVG only — no PDF and no PNG —
because there is no colour to fix.


VARIANT MATRIX
Colourway                             Standard         Icon          Small         App icon
Brand-OnLight                         yes              yes           yes           yes
Brand-OnDark                          yes              yes           yes           yes
Amber-OnLight                         yes              yes           yes           —
Amber-OnDark                          yes              yes           yes           —
Evergreen-OnLight                     yes              yes           yes           —
Evergreen-OnDark                      yes              yes           yes           —
Ink-OnLight                           yes              yes           yes           —
Ink-OnDark                            yes              yes           yes           —
Mono-Black                            yes              yes           yes           yes
Mono-White                            yes              yes           yes           yes
Mono-CurrentColor                     yes              yes           yes           —

Every colourway ships in all three cuts. The app-icon set is deliberately narrower: four colourways cover every
tile a desktop, dock or launcher needs, and the alternates would not be approved for that use.


EXPORT MATRIX
Location                                         Contents
01_Vector/SVG/ · all cuts                        11 colourways per cut
01_Vector/PDF/ · all cuts                        10 per cut — Mono-CurrentColor excluded, no fixed colour
02_Raster/PNG/Standard · Icon                    256, 512, 1024, 2048 px wide
02_Raster/PNG/Small                              32, 64, 128, 256 px wide
05_AppIcons/PNG/Standard · Icon                  128, 256, 512, 1024 px square
05_AppIcons/PNG/Small                            32, 64, 128, 256 px square
PNG widths name the exported pixel width. Every PNG is transparent, sRGB, and rendered directly from the
final vector at its own size — none is downscaled from a larger export. Export size and display size differ: a
256 px asset legitimately serves a 64 px slot on a high-density screen.
Vector PDF page geometry: artwork 288 pt (4 in) wide with 11.52 pt (4%) clear space on all four sides. Page
boxes are Standard 311.04 × 359.385 pt, Icon 311.04 × 389.613 pt, Small 311.04 × 395.899 pt — consistent
across every colourway within a cut. Artwork is filled paths throughout, with no raster, no live text and no
embedded fonts; the punched counters use the even-odd fill operator.
App-icon SVGs place the same artwork on a square 1244 × 1244 unit canvas, optically centred, with the
mark filling 86% of the canvas height.


FOLDER MAP AND FILE COUNTS
Path                                                                              Files
README.pdf                                                                            1
01_Vector/SVG/Standard/                                                              11
01_Vector/SVG/Icon/                                                                  11
01_Vector/SVG/Small/                                                                 11
01_Vector/PDF/Standard/                                                              10
01_Vector/PDF/Icon/                                                                  10
01_Vector/PDF/Small/                                                                 10
02_Raster/PNG/Standard/                                                              40
02_Raster/PNG/Icon/                                                                  40
02_Raster/PNG/Small/                                                                 40
03_Previews/                                                                          4
05_AppIcons/SVG/Standard/                                                             4
05_AppIcons/SVG/Icon/                                                                 4
05_AppIcons/SVG/Small/                                                                4
05_AppIcons/PNG/Standard/                                                            16
05_AppIcons/PNG/Icon/                                                                16
05_AppIcons/PNG/Small/                                                               16
Total                                                                              248


PREVIEWS
03_Previews/ holds Colorways.png, Cuts.png, Logo-Overview-OnLight.png and Logo-Overview-OnDark.png.
These are documentation, not production assets: the backgrounds they demonstrate are not shipped as
flattened PNG files, and Cuts.png renders the small sizes at true pixel size so the point at which detail fails is
visible rather than hidden.


INTENTIONAL OMISSIONS
04_Guidelines/ is absent by decision, not oversight — for a package of this size this README serves as the
usage documentation. The numbering gap between 03 and 05 is left visible rather than renumbered, so the
slot stays available in later revisions.
99_Source/ is absent because the delivered SVGs are the masters. There is no separate editable source, and
duplicating the SVGs into a source folder would only create two files to keep in step.


USAGE AND RESTRICTIONS
Keep clear space of at least 4% of the artwork width on all four sides. Place OnLight artwork on light grounds
and OnDark on dark ones. Choose one cut per context and respect its breakpoint.
Do not recolour, stretch, rotate, skew, outline or add effects to the mark. Do not rebuild it, redraw it, or
substitute a different music glyph. Do not flatten the PNGs onto a background colour. Do not mix cuts within
one layout, and do not scale a cut below its documented floor.

Tracks and Trails · Logo Asset Package v1.1 · 2026-08-25 · Assembled to the Logo Asset Packaging Standard rev. 1.1
