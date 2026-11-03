---
name: drawio
description: >
  Draws a diagram as draw.io XML a person pastes into a Confluence draw.io macro or opens in
  draw.io: a system's context, its components, a data flow or a deployment, laid out to be read,
  and checked before it is handed over. Use when asked to "draw a diagram", "make a draw.io
  diagram" or "diagram this system". Not for a chart of data, or a diagram in a Markdown file,
  where Mermaid renders without a paste.
argument-hint: "[context | components | flow | deployment] <what to draw> [output path]"
metadata:
  author: dev-tools
  version: 1.1.0
---

Every question follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. Other skills call
this one, `architecture-doc`, `design-doc` and `process-doc` among them, with what to draw and
where to write it.

## Options

| Option | Default |
|---|---|
| Kind | Read from the request: `context`, `components`, `flow` or `deployment`, as "One diagram, one question" says; asked when the request fits more than one |
| Content | What the caller or the person gives: the boxes and the lines between them, from a document, the code or a description. Nothing is drawn that the content does not name |
| Output | `.review/diagrams/<slug>.drawio`; a caller names its own path |

## One diagram, one question

A diagram answers one question, and its kind says which:

| Kind | The question | Holds |
|---|---|---|
| `context` | What does this system talk to? | The system as one box in the middle; each person, system and store on the other side of an interface around it; one line per interface, labeled with what crosses |
| `components` | What is it made of? | The system's boundary as a container, its parts inside, and the outside neighbors as small boxes at the edge where the lines leave |
| `flow` | What happens, in order? | Steps left to right, the trigger at the left; for data, stores beneath the step that reads or writes them; for a process people run, one horizontal lane per role (`swimlane`), each step in the lane of who does it, and a decision as a diamond (`rhombus`) with each way out labeled |
| `deployment` | Where does it run? | Accounts, networks or hosts as containers, the deployed parts inside them |

A request that asks two questions gets two diagrams, as two pages of one file. Past about
fifteen boxes a diagram stops being read: split it, by area or by step, and say how.

## Drawing it to be read

- **Every box and line comes from the content.** A name is the content's own word, matching
  the document it goes in. A line the content does not state is a question to the caller, not a
  guess.
- **Lines say what crosses.** A label is the data or the request ("raw records", "job request"),
  not "calls" or "uses". The arrow points the way the data goes; a request and its response
  that matter separately are two lines.
- **Shapes by kind, and few of them.** A rounded rectangle for a component or service; a
  cylinder (`shape=cylinder3`) for a store; a person (`shape=umlActor`) for a human user; a
  rectangle with a gray fill for a system outside the one drawn; a dashed container for the
  boundary of the system drawn. Name a cloud service in the label ("AWS Lambda: ingest") rather
  than with a vendor icon, whose style name renders as an empty box when it is wrong; use an icon
  only when the person asks and the caller gives the exact style.
- **Layout on a grid.** Grid size 10, every position and size a multiple of it; boxes 160 by 60
  unless a label needs more, the same size for the same kind; at least 40 between boxes and 80
  between a box and the next column. Orthogonal lines
  (`edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;`), with no line crossing a box and as few
  crossing each other as the layout allows; move a box before accepting a crossing.
- **Color carries meaning or nothing.** At most three fills besides white, each named in a legend
  at the bottom right; text dark on a light fill, 12 point or more. Inside versus outside the
  system is the usual meaning.
- **A title**, as a text cell at the top left: the system and the kind, and the date the content
  was true ("Ingest: context, 2026-10-25").

## The file

Uncompressed XML, so a person can read the diff and `drawio_check.py` can check it:

```xml
<mxfile host="drawio">
  <diagram name="Context" id="context">
    <mxGraphModel grid="1" gridSize="10" page="1" pageWidth="1100" pageHeight="850">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="ingest" value="Ingest" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">
          <mxGeometry x="400" y="200" width="160" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="archive" value="Archive" style="shape=cylinder3;whiteSpace=wrap;html=1;fillColor=#f5f5f5;" vertex="1" parent="1">
          <mxGeometry x="680" y="200" width="160" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="ingest-archive" value="raw files" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;" edge="1" parent="1" source="ingest" target="archive">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

Ids are short and say what the cell is (`ingest`, `ingest-archive`), unique in the file. Every
label escapes `&`, `<`, `>` and `"` as XML entities. A cell inside a container names the
container as its `parent`, with its position relative to the container.

## Steps

1. **Settle what to draw.** From the caller's or the person's content, list the boxes and the
   lines, each line with what crosses it, and the kind. When the content leaves a line or a box
   unclear, ask before drawing; a caller that is a skill gets the question back to ask.
2. **Write the file** with the Write tool at the output path, as
   `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`'s "Writing a file" says.
3. **Check it**: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/drawio_check.py" <path>`. Fix every
   failure and run it again; a warning is fixed or said why it stands. Then reread the file
   against "Drawing it to be read": each label the content's word, each line labeled, nothing
   crossing a box.
4. **Hand it over**: the path, the check's summary line, a list of the boxes and lines in words
   so the person can check the content without opening the file, and how to put it in place, as
   "Into Confluence" says. A caller gets the same and passes it on.

## Into Confluence

No tool uploads a diagram's attachment, so a person places it, once:

1. In the page editor, insert a draw.io diagram (`/draw.io`, or Insert, then draw.io Diagram).
2. In the draw.io editor, open Extras, then Edit Diagram; select all the XML there, paste the
   file's contents over it, and choose OK. File, then Import from, then Device, with the
   `.drawio` file, does the same.
3. Save the diagram with its title as the name, then publish the page.

A later write of the page keeps the diagram when its body carries the macro, as
`using-confluence`'s "Macros and mentions" says. To change a diagram already on a page, the
person exports its XML from Extras, then Edit Diagram, and gives it to this skill as the content
to change.

## Never

Draw a box or a line the content does not name. Hand over a file `drawio_check.py` fails. Upload
or attach a file anywhere.
