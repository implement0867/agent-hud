# agent-hud board UI: user-side findings (live two-agent test, 2026-10-24)

Board: project-a2c3d0. Task: release checklist for agent-hud 0.2. I act only through the browser.
Screenshots live in shots/

## Findings

### F1. Reaction controls exist only on hover and overlap the item text
- Did: moved the mouse over the first risk item.
- Happened: a small pill with three icons (check, cross, ?) appeared on hover only, floating over the end of the first line so the word "the" is covered (shots/01_hover_risk.png). Each icon is ~14 px.
- Expected: a visible affordance that reactions exist (at least on the card), and a pill that does not cover the text I am reacting to.
- Severity: annoying.
- Shot: shots/01_hover_risk.png

### F2. In the table, the hover "approve" check sits right next to the "Done" checkbox
- Did: hovered the "Write the changelog" row.
- Happened: the reaction pill (check / cross / ?) appears glued to the right of the Done checkbox (shots/01b_hover_row.png). Two check-like controls 20 px apart with different meanings (approve the step vs. the step is done).
- Expected: the reaction pill at the row start or clearly separated from the input column; or no table-row reactions at all when the row already has a checkbox.
- Severity: annoying.
- Shot: shots/01b_hover_row.png

### F3. Checklist table wastes width: Step column wraps to 4 lines while the card has 60 px of empty right margin
- Did: looked at the initial board.
- Happened: "Bump version in plugin and server" wraps to four lines in a ~70 px Step column; Owner/Hours/Done columns are fixed width and the right 60 px of the card are empty (shots/00_initial.png). The 7-row table is 450 px tall for 7 short lines.
- Expected: the text column takes the remaining width.
- Severity: annoying.
- Shot: shots/00_initial.png

### F4. Card edit/delete icons also appear only on hover, and nothing hints that cards are editable
- Did: hovered a card.
- Happened: pencil and trash icons fade in top-right (shots/01b_hover_row.png); also an unexplained purple ring appears on the right edge of the card mid-height (arrow anchor?) with no label.
- Expected: either persistent low-contrast controls, or a cursor/outline change that says "editable".
- Severity: nit.
- Shot: shots/01b_hover_row.png

### F5. Item ids in the UI do not match what I see: the second bullet is called "risks/3"
- Did: clicked "?" on the second risk bullet.
- Happened: the popover and the chat echo call it `risks/3` (shots/03_after_question_risk2.png, 04b). The first bullet presumably is risks/2 and the title risks/1. A person counts bullets, not blocks; the label is only meaningful to the agent and it leaks into my chat as `risks/3`.
- Expected: a human label ("Risks, item 2" or the quoted text), or no id at all.
- Severity: annoying.
- Shot: shots/04b_after_enter_comment.png

### F6. "?" opens a comment popover, "check" and "cross" do not: inconsistent, and Reject has no place for a reason
- Did: clicked check on risk 1 (badge only), "?" on risk 2 (popover with Approve/Reject/Question + Comment opened), cross on risk 4 (badge only).
- Happened: only Question opens the popover. To say why I rejected something I have to find out that the "?" (or clicking the badge?) is the way into the comment box. A reject without a reason is a useless signal to the agent.
- Expected: all three reactions open the same popover (or none do and there is a separate comment entry); Reject should invite a reason.
- Severity: annoying.
- Shot: shots/06b_after_reject_risk4.png

### F7. The reaction popover floats 300 px away from the item, in the gap between cards
- Did: clicked "?" on a risk bullet on the right-hand card.
- Happened: the popover appeared left of the card (x 450-740) while the item is at x 790-1050; my eye had to search for it (shots/03_after_question_risk2.png).
- Expected: anchored directly under or beside the item.
- Severity: nit.
- Shot: shots/03_after_question_risk2.png

### F8. Escape does not close the reaction popover
- Did: pressed Escape with the risks/3 popover open and its comment box focused.
- Happened: nothing (shots/05_after_escape.png); I had to hit the 12 px "x" in its corner.
- Expected: Escape closes a popover.
- Severity: annoying.
- Shot: shots/05_after_escape.png

### F9. A comment I typed shows up in the chat as a sent bubble, yet it is still "pending" in Send
- Did: posted a comment in the item popover.
- Happened: it appears immediately in the Chat panel as a blue bubble (looks sent), while the Send button says "Send 3" and the chat says "Your message also sends 3 changes." (shots/04b_after_enter_comment.png). I cannot tell whether the agent already has it.
- Expected: pending items look pending (grey/outlined, "not sent yet") until I press Send.
- Severity: annoying.
- Shot: shots/04b_after_enter_comment.png

### F10. The bottom toolbar re-centers and jumps left every time a pill is added
- Did: added reactions one by one.
- Happened: the toolbar grows by one pill per reaction type (check 1, cross 1, ? 1, comment 1) and re-centers, so every control moves 20-40 px between clicks (compare shots/00_initial.png, 02_after_approve_risk1.png, 06b_after_reject_risk4.png). The chat panel also grows upward with every message.
- Expected: stable positions; a single "4 changes" summary instead of four pills.
- Severity: nit.
- Shot: shots/06b_after_reject_risk4.png

### F11. Clicking into a table cell to type opens the reaction/comment popover for that row
- Did: picked an Owner and clicked the Hours cell in row 1; later every cell click in rows 2-7.
- Happened: each click opened the "checklist/N" popover (Approve/Reject/Question + Comment) to the right of the card (shots/08_row1_owner_hours.png, 10_table_filled.png). I never asked for it; it stays open after I move on and follows me row by row.
- Expected: focusing an input does not open a popover; the popover opens only from the reaction pill.
- Severity: annoying.
- Shot: shots/08_row1_owner_hours.png

### F12. Tab order walks through three invisible reaction buttons per row
- Did: Tab from row 1's Done checkbox, expecting the next row's Owner.
- Happened: focus went to the hidden "approve checklist/2" button (then reject, question) before the next row. Filling 7 rows by keyboard costs 21 extra Tabs through controls that are not even visible (shots/09_tab_from_done.png).
- Expected: reaction buttons are not in the tab order unless shown; Tab goes Owner -> Hours -> Done -> next Owner.
- Severity: annoying.
- Shot: shots/09_tab_from_done.png

### F13. "Send 19" but the toolbar pills only account for 4 of them
- Did: filled 7 owners, 7 hours, 1 done, plus 3 reactions and 1 comment.
- Happened: Send says 19, the pills say check 1, cross 1, ? 1, comment 1 (shots/10_table_filled.png). Nothing shows the 15 table edits as pending, and the cells look identical whether saved, pending, or sent.
- Expected: either the pills cover every pending change (e.g. "15 edits") or the count matches the pills.
- Severity: annoying.
- Shot: shots/10_table_filled.png

### F14. Hours is a number spinner, so "0.5" needs a decimal and up/down arrows show on hover; a 7 x 3 grid of unlabeled "---" placeholders
- Did: typed hours.
- Happened: works, but the placeholder "---" says nothing about the unit; the Owner select offers only "agent" / "user" ("user" is me, but I am not called that anywhere else on the page).
- Expected: placeholder "h" or "0", and my display name in the Owner list.
- Severity: nit.
- Shot: shots/10_table_filled.png

### F15. New note: Escape threatens to discard, clicking outside does not save, Save is a tiny text link half under the chat panel
- Did: double-clicked empty space (good: that works), typed a note, pressed Escape, then clicked outside.
- Happened: Escape shows "esc again discards your changes" (shots/12b_note_escape.png); clicking outside leaves the note in edit mode with "Unsaved changes Save Discard" as 12 px text links at the bottom edge, with "Discard" clipped by the Chat panel (shots/13_click_outside_note.png). Three actions to make one note.
- Expected: blur saves (like the table cells do); Escape saves-and-exits or at least asks once; Enter-to-save hint visible while typing.
- Severity: annoying.
- Shot: shots/13_click_outside_note.png

### F16. Saving my own note immediately opens an Approve/Reject/Question popover on my own note
- Did: clicked Save on the note.
- Happened: a "note-140a1398" popover with Approve/Reject/Question + Comment popped up left of the note (shots/14_note_saved.png). Reacting to my own text makes no sense, and the note is titled with a random id "note-140a1398" instead of nothing or its first line.
- Expected: no popover; a note has no id shown, or a label I chose.
- Severity: annoying.
- Shot: shots/14_note_saved.png

### F17. The note editor is monospace while every card is proportional; the new note is 390 x 120 px and lands under the Chat panel
- Did: double-clicked at (900,480), the only large free area.
- Happened: the note was created to the right of the click and is one-third hidden by the Chat panel; the chat panel is fixed and cannot be dismissed except by the small icon in its header (shots/12_note_typed.png).
- Expected: new note placed fully visible; chat panel collapsible by clicking its header.
- Severity: nit.
- Shot: shots/12_note_typed.png

### F18. Drawing an arrow: a quick drag from the dot pans the whole board instead; only a slow drag draws
- Did: hovered the note's text, dragged the purple dot at its right edge toward the checklist, twice at normal speed (shots/16b_dragging_arrow.png, 19_dragging_arrow.png), then once slowly with a 6 px first move (shots/22b_slow_drag_dot.png).
- Happened: the two normal drags panned the canvas 650 px and left me staring at empty board (I had to find the fit-all icon to recover). The slow drag drew the arrow. The dot itself also vanishes if you approach it from outside the card because it is only drawn while the item is hovered (shots/16_hover_anchor.png vs 18_hover_note.png).
- Expected: mousedown on the dot always starts an arrow; the dot stays visible while the pointer is on it; the board never pans from a drag that started on a control.
- Severity: blocker (the feature exists but a person will conclude it does not).
- Shot: shots/19_dragging_arrow.png

### F19. Clicking the purple dot opens the feedback popover, so the dot has two meanings
- Did: clicked (not dragged) the dot.
- Happened: the "note-140a1398/1" Approve/Reject/Question popover opened (shots/20_click_ring.png). Nothing on screen says the dot is for arrows; I only learned it from the "?" sheet ("Drag the dot on a part").
- Expected: a dot that looks like a connector (and a cursor change), or an arrow tool in the toolbar.
- Severity: annoying.
- Shot: shots/20_click_ring.png

### F20. Toolbar icons (history, keyboard, eraser, fit) have no label and no tooltip after 0.8 s hover
- Did: hovered the fit icon and the keyboard icon for 0.6-0.8 s.
- Happened: no tooltip (shots/17_hover_fit_icon.png, 21_hover_keyboard_icon.png). I guessed "fullscreen" for the fit icon; the eraser I still have not dared to click.
- Expected: a short tooltip, or text labels like "Note" has.
- Severity: annoying.
- Shot: shots/21_hover_keyboard_icon.png

### F21. Clicking the fit icon changes zoom to 90% and nothing says it will
- Did: clicked the expand-arrows icon to recover from the accidental pan.
- Happened: it fit all cards and the zoom readout went 100% -> 90% (shots/17b_after_fit.png). Fine, but the "1" / "0" shortcuts in the sheet are "Fit all cards" / "Reset the view", two concepts, one icon.
- Severity: nit.
- Shot: shots/17b_after_fit.png

### F22. The pencil icon on a card does nothing; "E" after selecting the card works
- Did: hovered the Risks card, clicked the pencil icon twice (shots/25_edit_risks.png, 26_pencil_again.png).
- Happened: nothing. Clicking the card header and pressing E opened the editor (shots/26c_after_E.png).
- Expected: the pencil opens the editor.
- Severity: blocker for mouse-only users (no visible way to edit).
- Shot: shots/26_pencil_again.png

### F23. Editing a card silently drops my pending question + comment on the item I touched
- Did: in the Risks editor appended " (no CI job exists yet)" to risk 2, which carried my "?" reaction and a comment, and pressed Ctrl+Enter.
- Happened: card shows "edited by you v2"; the "? 1" and "comment 1" pills vanished from the Send bar and the item's badges are gone (compare shots/27_edited_text.png and 27b_after_ctrl_enter.png). The editor's one-line grey footnote "saving moves the feedback on the parts you change to the history" was the only warning, in 10 px text. My comment still sits in the Chat panel as a blue bubble, so I cannot tell whether the agent will ever see it.
- Expected: reactions and comments stay attached to the item (same position in the list) or at least a confirm dialog "This will archive 2 pieces of feedback on the lines you changed".
- Severity: blocker (feedback lost without a clear confirmation).
- Shot: shots/27b_after_ctrl_enter.png

### F24. Card editor is raw markdown in monospace with no Save button; Ctrl+Enter is the only way out that keeps the text
- Did: pressed E, edited, looked for a Save control.
- Happened: none visible, only the footnote about history; Ctrl+Enter happened to work (I knew it from the "?" sheet where it is listed as "Send your changes", which is a different action!). Escape = discard.
- Expected: Save / Cancel buttons, and the same shortcut not meaning "save card" in one place and "send to agent" in another.
- Severity: annoying.
- Shot: shots/26c_after_E.png

### F25. Clicking a card header (to select it) opens the feedback popover for the whole card, so "Approve the whole Risks card" is one accidental click away
- Did: clicked the "risks" header text to select the card before pressing E.
- Happened: the card-level "risks" popover opened at the top left (shots/26b_click_header.png). Hovering the "Risks" heading also offers approve/reject/question on the heading itself (shots/24_hover_risks.png).
- Expected: selection without popover; reactions only on content items.
- Severity: annoying.
- Shot: shots/24_hover_risks.png

### F26. The pending-changes list (chevron next to Send) is written for the agent, not for me
- Did: clicked the chevron next to Send.
- Happened: a list like `checklist/2/2 = "agent"`, `checklist/2/3 = 1`, `approve risks/2 "The UI build is..."` (shots/29_send_chevron.png). Good news: my question and comment on risks/3 are still in it even though the pills dropped them (so F23 is partly a display bug). Bad news: nobody can read "checklist/4/3 = 1" as "Run make check: 1 h". The list is also cut at the bottom with no scroll hint.
- Expected: "Run make check: owner agent, 1 h", grouped per card; a count of hidden rows.
- Severity: annoying.
- Shot: shots/29_send_chevron.png

### F27. History panel covers the checklist card entirely and the "replaced" v1 is shown full size
- Did: pressed H.
- Happened: a 385 px panel slides over the left card; my archived question lives under the v1 card there (shots/28_history.png). Nothing in the main view tells me the item still has history (no clock badge on the item).
- Expected: a small "1 archived" marker on the edited item; panel docked without covering content, or the board shifts.
- Severity: nit.
- Shot: shots/28_history.png

### F28. After Send, the reaction pills (check 1, cross 1) stay in the toolbar as if still pending
- Did: sent round 1 from the chat box.
- Happened: Send went grey and the count disappeared, status says "working on your turn", but the "check 1" and "cross 1" pills are still there (shots/30b_after_send.png). Are they sent? Are they a tally? Nothing says.
- Expected: pills clear after Send or turn into a "sent" summary.
- Severity: annoying.
- Shot: shots/30b_after_send.png

### F29. Two Send controls: the toolbar "Send N" and the chat arrow; the chat footnote "Your message also sends N changes" is the only link between them
- Did: looked for where to send.
- Happened: the toolbar Send and the chat arrow both send; the chat one also takes a message, the toolbar one does not (shots/29_send_chevron.png, 30_typed_chat.png).
- Expected: one Send, with the message box next to it.
- Severity: annoying.
- Shot: shots/30_typed_chat.png

### F30. (Round 1 result) Agent answered in ~40 s, but nothing on the board marks what changed
- Did: waited after Send; the agent added three rows, removed a risk, bumped cards to v2/v3.
- Happened: the new rows look exactly like the old ones; the only cue is a tiny "v2" chip in the card header and the chat text (shots/poll_211638.png). The removed risk just vanished. My "?" badge on risk 2 turned into a "comment 1" badge without my doing anything.
- Expected: new/changed rows highlighted until I look at them (or a "3 rows added" chip), and removed items shown struck through once.
- Severity: annoying.
- Shot: shots/poll_211638.png

### F31. With 10 rows the Step column wraps one step to 7 lines and the card runs off the bottom of the screen
- Did: looked at checklist v2.
- Happened: "Run make check in a clean container (manual docker run, no CI yet)" is seven lines tall in a 60 px column; the table is now ~800 px tall and the last row is cut by the viewport (shots/poll_211638.png). This is F3 getting worse with content.
- Expected: text column gets the free width; card width grows with content or wraps the Owner/Hours/Done columns tighter.
- Severity: annoying.
- Shot: shots/poll_211638.png

### F32. Resizing the card works and fixes the table, but the arrow is then drawn straight through the card and its label covers the "Announce" Done checkbox
- Did: dragged the checklist card's corner handle 230 px to the right.
- Happened: the table re-flowed nicely (good). The arrow from my note did not re-route: it now crosses the card body and the "insert before" label sits on top of the last row's checkbox (shots/32c_resized.png). Resizing did not count as a change for Send, so I do not know if the agent sees the wider card.
- Expected: arrows stay outside cards; labels never cover controls.
- Severity: annoying.
- Shot: shots/32c_resized.png

### F33. The resize handle is a 10 px grey corner glyph with no hover cursor cue in the screenshot and no snap; the card's default width was simply wrong for a table
- Did: looked for how to widen the card; found the corner glyph by guessing.
- Severity: nit.
- Shot: shots/32_hover_resize_handle.png

### F34. BLOCKER: edits to a row the agent inserted are silently not queued when they happen to match an older row's values
- Did: in checklist v2, changed "Run the test suite" (agent, 0.5) to owner "user", hours 1. Toggled the owner agent->user again and retyped the hours 1.5 -> 1 to be sure (shots/34_round2_edits.png, 36b_retype_hours.png).
- Happened: the cells show user / 1, but Send stayed at 6 and the pending list never lists checklist/7. Edits to other rows (checklist/8/3 = 1, checklist/10/3 = 1, checklist/11/2 = "agent") were queued fine. Row 7 in v1 was "Publish the plugin" = user / 1, i.e. exactly the values I typed; the change tracker apparently diffs against the old row with the same number, not against what is on screen. Typing 1.5 did queue (then un-queued when I typed 1).
- Expected: anything I change in a cell is sent, full stop; the baseline is the version I am looking at.
- Severity: blocker (silent loss of user input; the agent will never learn I reassigned the step).
- Shot: shots/36b_retype_hours.png

### F35. The pending-changes list opened by itself this round and stays open over the note card
- Did: nothing; after the first change in round 2 the list appeared above Send and never closed (shots/34_round2_edits.png to 36b). Escape in round 1 had not closed it (F8 again), so it seems to have been "open" all along, just empty.
- Expected: a closed list stays closed; Escape closes it.
- Severity: annoying.
- Shot: shots/34b_question_build_ui.png

### F36. Pending-list entries for table rows show raw pipes: `question checklist/4 "Build the UI | | | "`
- Severity: nit.
- Shot: shots/34b_question_build_ui.png

### F37. The reaction popover for a table row opens on top of the Risks card and hides it
- Did: clicked "?" on "Build the UI".
- Happened: the popover covered the lower half of the Risks card I wanted to look at while writing the question (shots/34b_question_build_ui.png).
- Severity: annoying.
- Shot: shots/34b_question_build_ui.png

### F38. BLOCKER: clicking an item's comment badge rejects the item, because the hover pill appears exactly where the badges were
- Did: clicked the "comment 2" badge on "Build the UI" to read the agent's reply in context (shots/poll_212023.png shows the badge at x 598).
- Happened: on hover the badges are replaced by the check / cross / ? pill at the same coordinates, so my click landed on the cross: "reject checklist/9" is now queued and the row shows a red cross (shots/38_thread_build_ui.png). The thread did not open. One accidental click sends the wrong verdict to the agent.
- Expected: badges stay clickable and open the thread; the pill appears beside them, never under the pointer.
- Severity: blocker.
- Shot: shots/38_thread_build_ui.png

### F39. Opening an item's thread requires picking a verdict: the only entry is the check / cross / ? pill, and "?" replaces my Approve with Question
- Did: approved "Build the UI" (pill check), then clicked "?" to open the thread to read the agent's reply and answer it.
- Happened: the pending list now says only `question checklist/9` (shots/39b_thread_open.png); the approve was replaced. There is no neutral "open thread / reply" control, and the badge (F38) is not safely clickable.
- Expected: a reply affordance (the comment badge) that opens the thread without touching the verdict; a verdict is a separate toggle.
- Severity: blocker (in combination with F38).
- Shot: shots/39b_thread_open.png

### F40. The thread popover's comment box is covered by the pending-changes list
- Did: opened the thread on Build the UI with the pending list open.
- Happened: the "Comment" input at the bottom of the popover is half hidden under the pending list (shots/39b_thread_open.png); the popover also overlaps the note card.
- Severity: annoying.
- Shot: shots/39b_thread_open.png

### F41. An arrow cannot be selected or deleted once it is drawn: clicking its label selects the table row under it, clicking its line does nothing, Delete does nothing
- Did: clicked the "insert before" label (it sits on top of the Smoke-test row), pressed Delete; then clicked the visible line near the arrow head and pressed Delete (shots/41_click_arrow_label.png, 42b_after_delete.png).
- Happened: the first click opened the row's popover (checklist/11), the second click selected nothing; the arrow is still there both times. The "?" sheet promises "Delete: remove the card or arrow, with undo".
- Expected: clicking an arrow or its label selects it (highlight), Delete removes it with an undo toast.
- Severity: blocker (my stale arrow now points at the wrong row and I cannot remove it).
- Shot: shots/42b_after_delete.png

### F42. A "Clear the board" button lives in the main toolbar as an unlabeled eraser, between Shortcuts and Zoom, guarded only by a browser confirm()
- Did: after the checklist was agreed I finally clicked the eraser icon.
- Happened: a native confirm dialog opened ("Clear the board: the cards go to the history" is its title text); the dialog was dismissed and the board survived (shots/46_after_eraser_dialog.png). Up to that moment I had avoided the icon for three rounds because nothing said what it does. Only the icon turns red on hover.
- Expected: a destructive action goes in an overflow menu or next to the board-name menu, with a label, and an in-app confirm that names what will be cleared.
- Severity: annoying (could be blocker for a new user who taps it to "erase" a stray arrow).
- Shot: shots/46_after_eraser_dialog.png

### F43. (Correction to F20) The toolbar icons do carry native `title` tooltips, but they take >1 s to appear and never showed in any of my hovers
- Note: the titles are good ("Fit all cards (1)", "History (H)", "Clear the board: the cards go to the history"). They just should not be the only label. Keep F20 at nit.

### F44. The agent could delete my arrow; I could not (F41)
- Did: in round 3 I told the agent the arrow was stale; its reply says "I removed the stale 'insert before' arrow" and it is gone (shots/poll_212308.png).
- Happened: asymmetric powers on the same board. Also nothing on the board shows that the agent removed something of mine.
- Severity: annoying.
- Shot: shots/poll_212308.png

### F45. Cumulative chat panel: every round the panel grows, scrolls, and clips the top message mid-sentence; its collapse control is a 14 px icon
- Severity: nit.
- Shot: shots/47_final_ack_sent.png

## What was good

- Agent turnaround was fast: 40 s, 30 s and 30 s after each Send; status pill switched "your turn" / "working on your turn" reliably (shots/30b_after_send.png, poll_211638.png).
- Reactions persist as clear green / red / orange badges on the item after the hover pill goes away (shots/02b_hover_risk2.png).
- The chat echoes each item-level reply with its item tag, and the agent answered per item (shots/poll_211638.png); clicking a tag in chat is advertised ("Show checklist/9").
- Table cell edits commit on blur with no extra click; Tab moves through Owner > Hours > Done.
- Double-click on empty space makes a note where I clicked; N / H / 1 / 0 / +/- / A / R / Q / E shortcuts all worked once I found the sheet.
- The "?" sheet is complete and honest about every gesture (shots/21b_keyboard_help.png).
- Card resize re-flows the table nicely (shots/32c_resized.png); card drag is smooth and does not count as a "change".
- Fit-all (1) rescued me twice from an accidental pan.
- Version chips (v2, v3, "edited by you") and the History panel keep every earlier version with its feedback (shots/28_history.png).
- The pending-changes list, once found, is a truthful audit of what Send will deliver (shots/29_send_chevron.png).
- The agent kept my cell values when it inserted rows ("Your values moved with their rows") and corrected my arithmetic.

## Verdict

1. F34 - Cell edits on an agent-inserted row are silently dropped from Send when they equal a stale row's old values (user input lost, no feedback).
2. F38 + F39 - Clicking an item's comment badge rejects the item (hover pill replaces the badges under the pointer), and the only way to open a thread is to set a verdict.
3. F18 + F41 - Arrows: a normal-speed drag of the dot pans the board instead of drawing, and a drawn arrow can never be selected or deleted by the user.
4. F22 + F23 - The pencil icon does nothing (edit needs the E key), and saving an edit drops the pending question/comment on the edited line with only a 10 px footnote as warning.
5. F11 + F12 + F8 - Popovers open on every cell click, three hidden reaction buttons sit in the Tab order per row, and Escape closes neither popovers nor the pending list.
