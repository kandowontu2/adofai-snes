; The insertion guide is attached to the live entry floor, then projected
; through the same camera as the track. No frame packets or raster LOD.
; CPU-private temporaries, below relocated NMI code at $0800.
preview_lo=$07A0
preview_hi=$07A2
preview_mid=$07A4
preview_start=$07A6
preview_record=$07A8
preview_floor_x=$07AA
preview_floor_y=$07AC
preview_vertices=$07B0
preview_edge=$07BC
preview_piece=$07BE
preview_dx=$07C0
preview_dy=$07C2
preview_x=$07C4
preview_y=$07C6
.assert preview_y+2 <= neo_twirl_state_begin, error, "Planet preview overlaps persistent twirl state"
.export neo_far_planet_preview, neo_preview_circle, neo_preview_dash
.segment "NEOCODE"
neo_far_planet_preview:
    lda render_i
    cmp step
    jcc neo_preview_done_loop
    jeq neo_preview_done_loop
    lda selected_level
    asl a
    tax
    lda f:neo_preview_counts,x
    jeq neo_preview_done_loop
    sta preview_hi
    lda f:neo_preview_starts,x
    sta preview_start
    stz preview_lo
neo_preview_search_loop:
    lda preview_lo
    cmp preview_hi
    jcs neo_preview_done_loop
    clc
    adc preview_hi
    lsr a
    sta preview_mid
    asl a
    sta preview_record
    asl a
    asl a
    clc
    adc preview_record
    clc
    adc preview_start
    sta preview_record
    tax
    lda f:neo_preview_records,x
    cmp render_i
    beq neo_preview_found_loop
    bcc neo_preview_later_loop
    lda preview_mid
    sta preview_hi
    bra neo_preview_search_loop
neo_preview_later_loop:
    lda preview_mid
    inc a
    sta preview_lo
    bra neo_preview_search_loop
neo_preview_found_loop:
    lda render_i
    jsl neo_call_floor_position
    lda floor_x
    sta preview_floor_x
    lda floor_y
    sta preview_floor_y
    jsl neo_call_mode7_project
    lda sprite_x
    cmp #$F000
    jeq neo_preview_done_loop
    lda sprite_x
    clc
    adc #8
    sta preview_vertices
    lda sprite_y
    clc
    adc #8
    sta preview_vertices+2
    ldx preview_record
    lda preview_floor_x
    clc
    adc f:neo_preview_records+2,x
    sta floor_x
    lda preview_floor_y
    clc
    adc f:neo_preview_records+4,x
    sta floor_y
    jsl neo_call_mode7_project
    lda sprite_x
    cmp #$F000
    jeq neo_preview_done_loop
    lda sprite_x
    clc
    adc #8
    sta preview_vertices+4
    lda sprite_y
    clc
    adc #8
    sta preview_vertices+6
    ldx preview_record
    lda preview_floor_x
    clc
    adc f:neo_preview_records+6,x
    sta floor_x
    lda preview_floor_y
    clc
    adc f:neo_preview_records+8,x
    sta floor_y
    jsl neo_call_mode7_project
    lda sprite_x
    cmp #$F000
    jeq neo_preview_done_loop
    lda sprite_x
    clc
    adc #8
    sta preview_vertices+8
    lda sprite_y
    clc
    adc #8
    sta preview_vertices+10
    ; Use the existing scaled planet silhouette with a reserved all-white
    ; palette. It follows user zoom without overwriting editable artwork.
    lda #$3E
    sta sprite_attr
neo_preview_circle = *
    jsl neo_call_preview_orb
    lda #1
    sta object_small
    stz preview_edge
neo_preview_edge_loop:
    ldx preview_edge
    txa
    clc
    adc #4
    cmp #12
    bcc :+
    lda #0
:
    tay
    lda preview_vertices,y
    sec
    sbc preview_vertices,x
    sta preview_dx
    lda preview_vertices+2,y
    sec
    sbc preview_vertices+2,x
    sta preview_dy
    lda preview_vertices,x
    asl a
    asl a
    sta preview_x
    lda preview_vertices+2,x
    asl a
    asl a
    sta preview_y
    lda #3
    sta preview_piece
neo_preview_dash_loop:
    lda preview_x
    clc
    adc preview_dx
    sta preview_x
    cmp #$8000
    ror a
    cmp #$8000
    ror a
    sec
    sbc #4
    sta sprite_x
    lda preview_y
    clc
    adc preview_dy
    sta preview_y
    cmp #$8000
    ror a
    cmp #$8000
    ror a
    sec
    sbc #4
    sta sprite_y
    lda #216
    sta sprite_tile
    lda #$3F
    sta sprite_attr
neo_preview_dash = *
    jsl neo_call_sprite
    dec preview_piece
    bne neo_preview_dash_loop
    lda preview_edge
    clc
    adc #4
    sta preview_edge
    cmp #12
    jcc neo_preview_edge_loop
    stz object_small
neo_preview_done_loop:
    rtl
.segment "CODE"
