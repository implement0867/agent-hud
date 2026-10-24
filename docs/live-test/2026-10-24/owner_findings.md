# Findings from the owner, watching the live session

## A table with input columns is cramped and does not fill its card
- Seen: shots/owner_table_off_center.jpg (round 1, checklist card as the agent put it)
- The card has the plain default width (384 px). The table's columns end about 65 px short of the card's right edge, while the Step column is a third of the width and wraps "Bump version in plugin and server" onto four lines. The selected row's highlight runs the full card width, wider than the table it marks. The heading "Release checklist: agent-hud 0.2" wraps to two lines.
- Expected: a table with input columns gets a wide default, as code does (640 px); the table stretches to the card, and the text column takes the width the inputs leave.
- Severity: annoying, on every table the agent puts.

## Cards use fixed pixel defaults inside; the content should be fluid
- The card gets a fixed default width (384 px, or 640 with code), and the content inside keeps browser defaults: the table is width auto, so it shrinks to its inputs and leaves a gap, while the text column wraps. Nothing inside the card uses flex or grid; the header's marks strip is placed with a translate and a fixed span width.
- Expected: the card's default width comes from its content (fit-content between a minimum and a maximum); only a width the user drags is stored. The table fills the card, with the text column taking the remaining space (grid 1fr auto auto auto). Header, strip and resize handle are flex rows.
- The canvas keeps numbers: a card's position and dragged width on a zoomable board are coordinates, not layout.
- Severity: structural; the cause behind the cramped table.
