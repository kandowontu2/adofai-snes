; Menu-only artwork, split across bounded VBlanks. The art, credits and
; palette come from the chart, with no artwork work during play.
MENU_ART_PHASE=$0794
MENU_ART_LEVEL=$0796
MENU_ART_PTR=$0798
MENU_ART_OFFSET=$079C
.assert MENU_ART_OFFSET+2 <= $07A0, error, "Menu artwork overlaps planet preview scratch"
.segment "NEOCODE"
.export menu_art_vblank,menu_browser_layout
.a16
.i16
menu_art_scene:
    stx $4362
    ldx #.loword(hdma_hide)
    jml menu_art_hdma
menu_art_hdma:
    lda display_state
    bne @done
    ; Gameplay changes BG1's map width, atlas bank and scroll. Restore all
    ; menu addressing before exposing its freshly reloaded artwork.
    sep #$20
    .a8
    lda #$70
    sta $2107
.ifdef WIDE_SNAPSHOT_SUPPORT
    lda #$50
.else
    lda #$40
.endif
    sta $210B
    stz $210D
    stz $210D
    lda #$FF
    sta $210E
    sta $210E
    rep #$20
    .a16
    lda menu_depth
    beq @done
    lda MENU_ART_PHASE
    cmp #6
    bne @done
    ldx #.loword(hdma_menu_art)
@done:
    rtl
.a8
.i16
menu_art_vblank:
    php
    rep #$20
    .a16
    lda state
    jne @hide
    lda menu_depth
    jeq @hide
    lda selected_level
    cmp MENU_ART_LEVEL
    bne @new
    lda MENU_ART_PHASE
    beq @new
    cmp #6
    jeq @done
    bra @load
@new:
    lda selected_level
    sta MENU_ART_LEVEL
    lda #1
    sta MENU_ART_PHASE
    ; Leave the menu's first full HUD/transition upload its own VBlank.
    jmp @done
@load:
    lda MENU_ART_LEVEL
    asl a
    clc
    adc MENU_ART_LEVEL
    tax
    lda f:MENU_PREVIEW_DESCRIPTORS_ADDR,x
    sta MENU_ART_PTR
    sep #$20
    .a8
    lda f:MENU_PREVIEW_DESCRIPTORS_ADDR+2,x
    sta MENU_ART_PTR+2
    lda #$80
    sta $2115
    lda MENU_ART_PHASE
    cmp #1
    bne @art
    lda #1
    sta $4300
    lda #$18
    sta $4301
    ldx #$7000
    stx $2116
    ldx #.loword(MENU_PREVIEW_MAP_ADDR)
    stx $4302
    lda #^MENU_PREVIEW_MAP_ADDR
    sta $4304
    ldx #2048
    stx $4305
    lda #1
    sta $420B
    ; Tile zero belongs to the gameplay atlas and need not be blank.
    ; Reserve a menu-only blank glyph beyond art and credit characters.
    lda #9
    sta $4300
    ldx #$3A00
    stx $2116
    ldx #.loword(zero_word)
    stx $4302
    stz $4304
    ldx #32
    stx $4305
    lda #1
    sta $420B
    stz $4300
    lda #$22
    sta $4301
    lda #32
    sta $2121
    ldx MENU_ART_PTR
    stx $4302
    lda MENU_ART_PTR+2
    sta $4304
    ldx #32
    stx $4305
    lda #1
    sta $420B
    jmp @advance_heavy
@art:
    lda #1
    sta $4300
    lda #$18
    sta $4301
    lda MENU_ART_PTR+2
    sta $4304
    rep #$20
    .a16
    lda MENU_ART_PHASE
    cmp #4
    bcs @footer_offset
    lda #0
    ldx MENU_ART_PHASE
    cpx #2
    beq @offset
    lda #1536
    bra @offset
@footer_offset:
    lda #3072
    ldx MENU_ART_PHASE
    cpx #4
    beq @offset
    lda #4096
@offset:
    sta MENU_ART_OFFSET
    clc
    adc #32
    adc MENU_ART_PTR
    sta $4302
    lda MENU_ART_OFFSET
    lsr a
    clc
    adc #$3000
    sta $2116
    lda MENU_ART_PHASE
    cmp #4
    ldx #2048
    bcs @footer_size
    ldx #1536
    bra @upload
@footer_size:
    ldx #1024
@upload:
    stx $4305
    sep #$20
    .a8
    lda #1
    sta $420B
@advance:
    rep #$20
    .a16
    inc MENU_ART_PHASE
    bra @done
@advance_heavy:
    rep #$20
    .a16
    inc MENU_ART_PHASE
    plp
    sec
    rtl
@hide:
    stz MENU_ART_PHASE
    lda #$FFFF
    sta MENU_ART_LEVEL
@done:
    plp
    clc
    rtl

.a16
menu_browser_layout:
    phx
    phy
    lda #0
    ldx #36
@clear_right:
    .repeat 9,row
    sta HUD+(6+row)*64,x
    .endrepeat
    inx
    inx
    cpx #64
    bcc @clear_right
    ldx #16*64
@clear_footer:
    sta HUD,x
    inx
    inx
    cpx #28*64
    bcc @clear_footer
.ifdef LEVEL_TITLES_ADDR
    lda selected_level
    asl a
    clc
    adc selected_level
    sta menu_row
    lda selected_level
    .repeat 5
    asl a
    .endrepeat
    sec
    sbc menu_row
    tax
    ldy #16*64+2
    sep #$20
    .a8
@title:
    lda f:LEVEL_TITLES_ADDR,x
    beq @lines
    sta HUD,y
    lda #$3C
    sta HUD+1,y
    inx
    iny
    iny
    bra @title
.endif
@lines:
    .macro BROWSER_LINE name,row
    ldx #name-menu_browser_strings
    ldy #row*64
    jsr menu_browser_line
    .endmacro
    BROWSER_LINE menu_browser_navigation,17
    BROWSER_LINE menu_browser_start,20
    BROWSER_LINE menu_browser_modes,21
    BROWSER_LINE menu_browser_controls,22
    BROWSER_LINE menu_browser_speed,23
    BROWSER_LINE menu_browser_offset,24
    rep #$20
    .a16
    ply
    plx
    rtl
.a8
menu_browser_line:
    sep #$20
@character:
    lda f:menu_browser_strings,x
    beq @done
    sta HUD,y
    lda #$3C
    sta HUD+1,y
    inx
    iny
    iny
    bra @character
@done:
    rts
menu_browser_strings:
menu_browser_navigation: .byte "       UP / DOWN SELECT",0
menu_browser_start: .byte "         START TO PLAY",0
menu_browser_modes: .byte "      X PRACTICE   Y WATCH",0
menu_browser_controls: .byte "     SELECT OPTIONS  B BACK",0
menu_browser_speed: .byte "     L / R SPEED: 1.0X",0
menu_browser_offset: .byte "    OFFSET: +00 FRAMES  < >",0
.segment "CODE"
