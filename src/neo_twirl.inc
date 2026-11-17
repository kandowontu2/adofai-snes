.segment "NEOCODE"
; Native three-planet twirls interpolate actual and reflected orbit vectors.
; Curves are compiled once; the independent SNES multiplier leaves the SA-1
; cache worker running. Ordinary notes take only the flag-test fast path.
neo_far_twirl_orbit:
.ifdef SA1_BUILD
    lda state
    cmp #1
    jcc @done
    cmp #5
    jcs @done
    ldx step
    lda f:NOTE_FLAGS,x
    bit #4
    jeq @done
    lda f:NOTE_CCW,x
    bit #2
    jeq @done
    lda step
    inc a
    cmp neo_twirl_cache_step
    bne @lookup
    lda selected_level
    cmp neo_twirl_cache_level
    bne @lookup
    ldx neo_twirl_cache_record
    cpx #$FFFF
    jeq @done
    bra @sample
@lookup:
    lda step
    inc a
    sta neo_twirl_cache_step
    lda selected_level
    sta neo_twirl_cache_level
    lda #$FFFF
    sta neo_twirl_cache_record
    lda selected_level
    asl a
    tax
    lda f:neo_twirl_counts,x
    jeq @done
    sta neo_twirl_hi
    stz neo_twirl_lo
    lda f:neo_twirl_starts,x
    sta scratch2
@find:
    lda neo_twirl_lo
    cmp neo_twirl_hi
    jcs @done
    clc
    adc neo_twirl_hi
    lsr a
    sta neo_twirl_mid
    asl a
    asl a
    asl a
    clc
    adc scratch2
    tax
    lda f:neo_twirl_records,x
    cmp step
    beq @found
    bcs @earlier
    lda neo_twirl_mid
    inc a
    sta neo_twirl_lo
    bra @find
@earlier:
    lda neo_twirl_mid
    sta neo_twirl_hi
    bra @find
@found:
    stx neo_twirl_cache_record
@sample:
    lda chart_time
    sec
    sbc f:neo_twirl_records+2,x
    bpl :+
    lda #0
:
    cmp f:neo_twirl_records+4,x
    jcs @done
    clc
    adc f:neo_twirl_records+6,x
    asl a
    tax
    lda f:neo_twirl_a,x
    sta neo_twirl_m00
    lda f:neo_twirl_b,x
    sta neo_twirl_m01
    lda f:neo_twirl_d,x
    sta neo_twirl_m11
    lda orbit_x
    sta neo_twirl_x
    lda orbit_y
    sta neo_twirl_y
    lda neo_twirl_x
    ldx neo_twirl_m00
    jsl neo_deco_multiply
    sta orbit_x
    lda neo_twirl_y
    ldx neo_twirl_m01
    jsl neo_deco_multiply
    clc
    adc orbit_x
    sta orbit_x
    lda neo_twirl_x
    ldx neo_twirl_m01
    jsl neo_deco_multiply
    sta orbit_y
    lda neo_twirl_y
    ldx neo_twirl_m11
    jsl neo_deco_multiply
    clc
    adc orbit_y
    sta orbit_y
@done:
.endif
.export neo_twirl_complete
neo_twirl_complete = *
    rtl
.segment "CODE"
