Screen question: How does a candidate's frame label change across the full match?
The screen is for an analyst checking one candidate submission at a time.
The input is a CSV with the frame and label fields.
The local contract expects 199,319 frames indexed from 0 through 199,318.
The allowed labels are H, A, D, and X.
H and A identify home and away possession; D marks dead ball; X is uncertain or abstained.
The match assets and all ground truth stay outside this prototype.
The main action is selecting a candidate CSV from local storage.
Counts and run boundaries are computed only from the selected file.
Run lengths are shown in frames because no frame rate is assumed here.
The signature element is a full-match label strip with exact frame selection.
The face is a low-chroma pitch-green frame around a white analysis sheet.
The analytics line-chart pattern was adapted because these labels are categorical, not a time series.
The public or private score is never shown or used to tune the display.
