; Live OBJ labels share one neutral font and palette for both answers.
; New runs and checkpoint attempts roll four independent variants. All
; positions use the live track projection.
.export neo_math_before_label, neo_math_after_label
.export neo_math_group, neo_math_label
.segment "BSS"
neo_math_seed: .res 2
neo_math_choices: .res 8
; CPU-only draw temporaries, above sprite_exact_room's scratch and below
; relocated NMI code. The SA-1 has its own separate IRAM at these addresses.
neo_math_row=$0780
neo_math_left=$0782
neo_math_count=$0784
neo_math_pool=$0786
neo_math_label=$0788
neo_math_cursor=$078A
neo_math_base_x=$078C
neo_math_base_y=$078E
neo_math_group=$0790
neo_math_mode=$0792

.segment "NEOCODE"
; Midspins are automatic, zero-duration markers, not planet pivots. A
; slightly late manual tap can leave logical step on the marker for a frame.
; Keep drawing the real orbit after it, without accepting/scoring that tap.
; This matters when the static marker is above a moving platform.
neo_far_visual_step:
neo_visual_next:
    pha
    tax
    lda f:NOTE_FLAGS,x
    and #16
    beq neo_visual_ready
    pla
    cmp last_note
    bcs neo_visual_done
    inc a
    bra neo_visual_next
neo_visual_ready:
    pla
neo_visual_done:
    rtl

.macro neo_graphics addr,dest,size
    lda #.loword(addr)
    sta transfer_ptr
    sep #$20
    .a8
    lda #.bankbyte(addr)
    sta transfer_ptr+2
    rep #$20
    .a16
    lda #dest
    sta transfer_dest
    lda #size
    sta transfer_len
    jsl neo_call_upload_vram
.endmacro
neo_math_load_graphics:
    neo_graphics NEO_OBJECTS_ADDR,$7C00,2048
    ; Last 22 Neo OBJ tiles: beyond the 16x16 meteor's bottom row, without
    ; touching the HUD map at $7800 or the track map/spill arena at $7000.
    neo_graphics NEO_MATH_FONT_ADDR,$7EA0,704
    rtl

neo_math_randomize:
    lda neo_math_seed
    eor clock_ticks
    eor #$A53D
    bne :+
    inc a
:
    ldx #0
neo_math_choice:
    .repeat 5
    lsr a
    bcc :+
    eor #$B400
:
    .endrepeat
    sta neo_math_seed
    and #3
    sta neo_math_choices,x
    lda neo_math_seed
    inx
    inx
    cpx #8
    bcc neo_math_choice
    rtl

neo_math_draw:
    lda selected_level
    asl a
    tax
    lda f:neo_math_counts,x
    jne neo_math_active
    rts
neo_math_active:
    sta neo_math_count
    lda f:neo_math_starts,x
    sta neo_math_row
    lda f:neo_math_modes,x
    sta neo_math_mode
neo_math_record:
    ldx neo_math_row
    lda chart_time
    cmp f:neo_math_records+2,x
    jcc neo_math_next
    cmp f:neo_math_records+4,x
    jcs neo_math_next
    lda f:neo_math_records+18,x
    asl a
    sta neo_math_group
    lda #0
    ldy speed_tenths
    cpy #13
    bcc :+
    lda #8
    cpy #16
    bcc :+
    lda #16
    cpy #20
    bcc :+
    lda #24
:
    clc
    adc neo_math_mode
    clc
    adc neo_math_group
    tax
    lda f:neo_math_pool_choices,x
    sta neo_math_pool
    ldx neo_math_group
    lda neo_math_choices,x
    asl a
    sta neo_math_left
    asl a
    clc
    adc neo_math_left
    asl a
    asl a
    asl a
    clc
    adc neo_math_pool
    sta neo_math_pool
    ldx neo_math_row
    lda f:neo_math_records,x
    jsl neo_call_floor_position
    lda floor_x
    sta neo_math_base_x
    lda floor_y
    sta neo_math_base_y
    stz neo_math_label
    lda #1
    sta object_small
neo_math_label_loop:
    lda neo_math_label
    asl a
    asl a
    clc
    adc neo_math_row
    tax
    lda f:neo_math_records+6,x
    clc
    adc neo_math_base_x
    sta floor_x
    lda f:neo_math_records+8,x
    clc
    adc neo_math_base_y
    sta floor_y
    jsl neo_call_mode7_project
    ; mode7_project returns the top left of a 16-pixel object. Center the
    ; eight-pixel letters about that same world-space anchor.
    lda sprite_y
    clc
    adc #4
    sta sprite_y
    lda neo_math_label
    .repeat 4
    asl a
    .endrepeat
    clc
    adc neo_math_pool
    sta neo_math_cursor
    tax
    ldy #0
neo_math_length:
    lda f:neo_math_pools,x
    and #255
    beq neo_math_center
    inx
    iny
    cpy #16
    bcc neo_math_length
neo_math_center:
    tya
    asl a
    sty neo_math_left
    clc
    adc neo_math_left
    sta neo_math_left
    lda sprite_x
    clc
    adc #8
    sec
    sbc neo_math_left
neo_math_before_label = *
    sta sprite_x
neo_math_character:
    ldx neo_math_cursor
    lda f:neo_math_pools,x
    and #255
    beq neo_math_label_done
    tax
    lda f:neo_math_font_tiles,x
    and #255
    sta sprite_tile
    lda #$35
    ldx neo_math_group
    cpx #4
    bcc :+
    lda #$33
:
    sta sprite_attr
    jsl neo_call_sprite
    lda sprite_x
    clc
    adc #6
    sta sprite_x
    inc neo_math_cursor
    bra neo_math_character
neo_math_label_done:
neo_math_after_label = *
    inc neo_math_label
    lda neo_math_label
    cmp #3
    jcc neo_math_label_loop
    stz object_small
neo_math_next:
    lda neo_math_row
    clc
    adc #20
    sta neo_math_row
    dec neo_math_count
    jne neo_math_record
    rts
.segment "CODE"
