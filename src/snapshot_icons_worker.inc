; Full snapshot charts: project and emit all essential symbols on SA-1.
; The CPU supplies its existing OAM prefix once. Exact scanline occupancy
; is charged incrementally instead of rescanning OAM for every icon.
SNAPSHOT_ICON_LINES=$0100
.assert SNAPSHOT_ICON_LINES+288 <= $0480, error, "Icon counters overlap copy-parent cache"
worker_snapshot_icons:
    lda M7_CACHE_CODE_VALID
    cmp #6
    beq @hot
    phb
    ldx #__HOTICONS_LOAD__
    ldy #__HOTICONS_RUN__
    lda #__HOTICONS_SIZE__-1
    mvn #$01,#$00
    plb
    phb
    ldx #__HOTICONSCAN_LOAD__
    ldy #__HOTICONSCAN_RUN__
    lda #__HOTICONSCAN_SIZE__-1
    mvn #$01,#$00
    plb
    lda #0
    sta M7_ROW_CODE_VALID
    lda #6
    sta M7_CACHE_CODE_VALID
@hot:
    jmp worker_snapshot_icons_hot
.segment "HOTICONSCAN"
worker_snapshot_icons_hot:
    lda #0
    sta f:SPILL_OAM_BYTES
    ldx #0
@high:
    sta f:SPILL_OAM_HIGH,x
    inx
    inx
    cpx #32
    bcc @high
    ldx #0
@clear:
    sta a:SNAPSHOT_ICON_LINES,x
    inx
    inx
    cpx #288
    bcc @clear
    stz map_x
@prefix:
    ldx map_x
    txa
    cmp f:SPILL_OAM_PREFIX
    bcs @floors
    lda f:SNAPSHOT_ICON_PREFIX+1,x
    and #255
    sta view_y
    txa
    and #12
    lsr a
    tax
    lda f:$010000+mode1_icon_sizes,x
    sta scratch
    lda map_x
    lsr a
    lsr a
    lsr a
    lsr a
    tax
    lda f:SNAPSHOT_ICON_PREFIX+512,x
    and scratch
    beq @small
    lda #16
    bra @height
@small:
    lda #8
@height:
    sta view_rows
    lsr a
    lsr a
    lsr a
    xba
    inc a
    sta map_run
    jsr worker_snapshot_icon_interval
    bcs @prefix_next
    jsr worker_snapshot_icon_charge
@prefix_next:
    lda map_x
    clc
    adc #4
    sta map_x
    bra @prefix
@floors:
    stz map_x
@floor:
    lda map_x
    cmp f:SYMBOL_VISIBLE_COUNT
    jcs @done
    tax
    lda f:SYMBOL_SCREEN_Y,x
    sta view_count
    lda f:SYMBOL_VISIBLE,x
    sta map_y
    tax
    lda f:NATIVE_ALPHA,x
    and #255
    jeq @next
    lda f:SNAPSHOT_ICON_INFO,x
    and #255
    sta map_base_ptr
    and #3
    beq @reverse
    cmp #1
    beq @rabbit
    lda #$3422
    bra @speed
@rabbit:
    lda #$3220
@speed:
    sta map_dest
    jsr @position
    jsr worker_snapshot_icon_sprite
@reverse:
    lda map_base_ptr
    and #12
    beq @special
    cmp #4
    beq @clockwise
    lda #$3426
    bra @twirl
@clockwise:
    lda #$3224
@twirl:
    sta map_dest
    jsr @position
    lda map_base_ptr
    and #3
    beq :+
    lda view_y
    sec
    sbc #14
    sta view_y
:
    jsr worker_snapshot_icon_sprite
@special:
    lda map_base_ptr
    and #$70
    beq @checkpoint
    cmp #$70
    beq @checkpoint
    lsr a
    lsr a
    lsr a
    tax
    lda f:$010000+@kinds-2,x
    sta map_dest
    jsr @position
    lda map_base_ptr
    and #$70
    cmp #$20
    bne :+
    inc view_x
:
    jsr worker_snapshot_icon_sprite
@checkpoint:
    lda map_base_ptr
    and #128
    beq @next
    lda f:M1_ICON_ATTACK
    bne @next
    lda #$364A
    sta map_dest
    lda f:M1_ICON_CHECKPOINT
    cmp #$FFFF
    beq :+
    cmp map_y
    bcc :+
    inc map_dest
    inc map_dest
:
    jsr @position
    lda map_base_ptr
    and #127
    beq :+
    lda view_y
    sec
    sbc #14
    sta view_y
:
    jsr worker_snapshot_icon_sprite
@next:
    inc map_x
    inc map_x
    jmp @floor
@done:
    rts
@position:
    ldx map_x
    lda f:SYMBOL_SCREEN_X,x
    sta view_x
    lda view_count
    sta view_y
    rts
@kinds:
    .word $3268,$346A,$326C,$346C,$366E,$3648

; A height, view_y top. Return [X,scratch2) clipped to playfield;
; carry set for an empty interval. Prefix objects can straddle the HUD.
.segment "HOTICONS"
worker_snapshot_icon_interval:
    lda view_y
    clc
    adc view_rows
    cmp #33
    bcc @empty
    cmp #176
    bcc :+
    lda #176
:
    sec
    sbc #32
    asl a
    sta scratch2
    lda view_y
    cmp #32
    bcs :+
    lda #32
:
    sec
    sbc #32
    asl a
    cmp scratch2
    bcs @empty
    tax
    clc
    rts
@empty:
    sec
    rts

worker_snapshot_icon_charge:
@line:
    lda a:SNAPSHOT_ICON_LINES,x
    clc
    adc map_run
    sta a:SNAPSHOT_ICON_LINES,x
    inx
    inx
    cpx scratch2
    bcc @line
    rts

worker_snapshot_icon_sprite:
    lda view_x
    cmp #$FFF1
    bcs @x_inside
    cmp #256
    jcs @done
@x_inside:
    lda view_y
    cmp #32
    jcc @done
    cmp #177
    jcs @done
    lda f:SPILL_OAM_BYTES
    clc
    adc f:SPILL_OAM_PREFIX
    cmp #512
    jcs @done
    sta map_left
    lda #16
    sta view_rows
    lda #$0201
    sta map_run
    jsr worker_snapshot_icon_interval
    bcs @outside
    stx scratch
@check:
    lda a:SNAPSHOT_ICON_LINES,x
    cmp #$2100
    bcs @reject
    and #255
    cmp #32
    bcs @reject
    inx
    inx
    cpx scratch2
    bcc @check
    ldx scratch
    jsr worker_snapshot_icon_charge
@outside:
    ; Keep the CPU's conservative bins in sync for subsequent optional
    ; effects, while exact occupancy decides essential symbol admission.
    lda view_y
    lsr a
    lsr a
    lsr a
    tax
    lda view_y
    clc
    adc #15
    lsr a
    lsr a
    lsr a
    sta scratch2
    jmp snapshot_icon_coarse_charge
@reject:
@done:
    rts


snapshot_icon_coarse_charge:
    sep #$20
    .a8
snapshot_icon_charge:
    lda f:SPILL_OAM_BUDGET,x
    inc a
    inc a
    sta f:SPILL_OAM_BUDGET,x
    inx
    cpx scratch2
    bcc snapshot_icon_charge
    beq snapshot_icon_charge
    rep #$20
    .a16
snapshot_icon_append:
    lda f:SPILL_OAM_BYTES
    tax
    lda view_y
    xba
    and #$FF00
    sta scratch
    lda view_x
    and #255
    ora scratch
    sta f:SPILL_OAM_OUT,x
    lda map_dest
    sta f:SPILL_OAM_OUT+2,x
    lda map_left
    and #12
    lsr a
    tax
    lda f:$010000+snapshot_icon_sizes,x
    sta scratch
    lda view_x
    bpl snapshot_icon_high
    lda scratch
    lsr a
    ora scratch
    sta scratch
snapshot_icon_high:
    lda map_left
    .repeat 4
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda f:SPILL_OAM_HIGH,x
    ora scratch
    sta f:SPILL_OAM_HIGH,x
    rep #$20
    .a16
    lda f:SPILL_OAM_BYTES
    clc
    adc #4
    sta f:SPILL_OAM_BYTES
snapshot_icon_done:
    rts
snapshot_icon_sizes:
    .word 2,8,32,128

.segment "CODE"
