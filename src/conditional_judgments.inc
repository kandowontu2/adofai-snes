.segment "NEOCODE"
; Native angular judgments for charts whose conditional hazards depend on
; them. ScaleMargin scales the angular Pure/Perfect windows, never XPerfect;
; the real-time minimums remain in force. Legacy charts keep their grading.
; A = absolute chart-frame error (8.8), C = supported, A = grade if supported.
conditional_classify_hit:
    sta judge_abs
    ldx #0
@level:
    lda selected_level
    cmp f:conditional_levels,x
    beq @native
    inx
    inx
    cpx #CONDITIONAL_LEVEL_COUNT*2
    bcc @level
    lda judge_abs
    clc
    rtl
@native:
    lda judge_abs
    sta math_a
    lda #10
    sta math_b
    jsl neo_call_multiply_points
    lda speed_tenths
    sta math_b
    jsl neo_call_divide32
    lda math_lo
    sta judge_abs
    ; 12.5 degrees * 256 angle units / 360 * 65536.
    lda #.loword(582542)
    sta math_lo
    lda #.hiword(582542)
    sta math_hi
    lda #256
    jsr conditional_window
    cmp judge_abs
    bcc @pure
    lda #4
    sec
    rtl
@pure:
    ; 30 degrees, with percentage margin; rounded to < 0.001 frame.
    lda #13981
    sta math_a
    lda input_margin
    sta math_b
    jsl neo_call_multiply_points
    lda #385                 ; 25 ms at the NTSC frame rate
    jsr conditional_window
    cmp judge_abs
    bcc @ordinary
    lda #3
    bra @side
@ordinary:
    ; Native Perfect minimum = max(30 ms / speed, 25 ms).
    lda #4615
    sta math_lo
    stz math_hi
    lda speed_tenths
    sta math_b
    jsl neo_call_divide32
    lda math_lo
    cmp #385
    bcs :+
    lda #385
:
    pha
    lda #20972
    sta math_a
    lda input_margin
    sta math_b
    jsl neo_call_multiply_points
    pla
    jsr conditional_window
    cmp judge_abs
    bcc @rough
    lda #2
    bra @side
@rough:
    lda #1
@side:
    ldx judge_signed
    bmi @done
    sta scratch
    lda #8
    sec
    sbc scratch
@done:
    sec
    rtl

; Convert angular numerator in math_hi:math_lo to real 8.8 frames,
; clamping to the real-time minimum in A. Called only for player landings.
conditional_window:
    pha
    lda step
    asl a
    tax
    lda f:NOTE_RATE,x
    bpl :+
    eor #$FFFF
    inc a
:
    bne :+
    inc a
:
    sta math_b
    jsl neo_call_divide32
    lda math_lo
    sta math_a
    lda #10
    sta math_b
    jsl neo_call_multiply_points
    lda speed_tenths
    sta math_b
    jsl neo_call_divide32
    pla
    cmp math_lo
    bcs :+
    lda math_lo
:
    rts

; A = conditional floor. Ordinary levels exit immediately.
conditional_requires_perfect:
    sta scratch2
    ldx #0
@level:
    lda selected_level
    cmp f:conditional_levels,x
    beq @found
    inx
    inx
    cpx #CONDITIONAL_LEVEL_COUNT*2
    bcc @level
@no:
    clc
    rtl
@found:
    lda f:conditional_ends,x
    sta scratch
    lda f:conditional_starts,x
    tax
@range:
    lda scratch2
    cmp f:conditional_ranges,x
    bcc @no
    cmp f:conditional_ranges+2,x
    bcc @yes
    inx
    inx
    inx
    inx
    cpx scratch
    bcc @range
    bra @no
@yes:
    sec
    rtl
.segment "CODE"
