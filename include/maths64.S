//
// Copyright (c) 2014 Jason L. Wright (jason@thought.net)
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions
// are met:
// 1. Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
// 2. Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in the
//    documentation and/or other materials provided with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
// IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
// WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
// INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
// HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
// ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
//

// basic assembly math routines for DARPA Cyber Grand Challenge (64-bit)

#ifdef APPLE
.macro .type
.endm

.macro .size
.endm

// OSX symbols need a leading underscore
# define SYM(x) _##x

#else
# define SYM(x) x
#endif // APPLE

.macro ENTER base
    .global \base, \base\()f, \base\()l
    .type \base, @function
    .type \base\()f, @function
    .type \base\()l, @function
.endm

.macro END base
    .size \base, . - \base
    .size \base\()f, . - \base\()f
    .size \base\()l, . - \base\()l
.endm

ENTER SYM(cgc_sin)
SYM(cgc_sinl):
    fldt    (%rsp)
    fsin
    fnstsw  %ax
    sahf
    jp      1f
    ret
1:
    call    SYM(cgc_twopi_rem)
    fsin
    ret
SYM(cgc_sinf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fsin
    fnstsw  %ax
    sahf
    jp      1f
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
1:
    call    SYM(cgc_twopi_rem)
    fsin
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_sin):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fsin
    fnstsw  %ax
    sahf
    jp      1f
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
1:
    call    SYM(cgc_twopi_rem)
    fsin
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_sin)

ENTER SYM(cgc_cos)
SYM(cgc_cosl):
    fldt    (%rsp)
    fcos
    fnstsw  %ax
    sahf
    jp      1f
    ret
1:
    call    SYM(cgc_twopi_rem)
    fcos
    ret
SYM(cgc_cosf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fcos
    fnstsw  %ax
    sahf
    jp      1f
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
1:
    call    SYM(cgc_twopi_rem)
    fcos
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_cos):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fcos
    fnstsw  %ax
    sahf
    jp      1f
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
1:
    call    SYM(cgc_twopi_rem)
    fcos
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_cos)

ENTER SYM(cgc_tan)
SYM(cgc_tanl):
    fldt    (%rsp)
    fptan
    fnstsw  %ax
    sahf
    jp      1f
    fstp    %st(0)
    ret
1:
    call    SYM(cgc_twopi_rem)
    fptan
    fstp    %st(0)
    ret
SYM(cgc_tanf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fptan
    fnstsw  %ax
    sahf
    jp      1f
    fstp    %st(0)
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
1:
    call    SYM(cgc_twopi_rem)
    fptan
    fstp    %st(0)
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_tan):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fptan
    fnstsw  %ax
    sahf
    jp      1f
    fstp    %st(0)
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
1:
    call    SYM(cgc_twopi_rem)
    fptan
    fstp    %st(0)
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_tan)

.type SYM(cgc_twopi_rem), @function
SYM(cgc_twopi_rem):
    fldpi
    fadd    %st(0)
    fxch    %st(1)
1:
    fprem
    fnstsw  %ax
    sahf
    jp      1b
    fstp    %st(1)
    ret
.size    SYM(cgc_twopi_rem), . - SYM(cgc_twopi_rem)

ENTER SYM(cgc_remainder)
SYM(cgc_remainderl):
    fldt    16(%rsp)
    fldt    (%rsp)
1:
    fprem1
    fstsw   %ax
    sahf
    jp      1b
    fstp    %st(1)
    ret
SYM(cgc_remainderf):
    sub     $16, %rsp
    movss   %xmm1, 8(%rsp)
    movss   %xmm0, (%rsp)
    flds    8(%rsp)
    flds    (%rsp)
1:
    fprem1
    fstsw   %ax
    sahf
    jp      1b
    fstp    %st(1)
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $16, %rsp
    ret
SYM(cgc_remainder):
    sub     $16, %rsp
    movsd   %xmm1, 8(%rsp)
    movsd   %xmm0, (%rsp)
    fldl    8(%rsp)
    fldl    (%rsp)
1:
    fprem1
    fstsw   %ax
    sahf
    jp      1b
    fstp    %st(1)
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $16, %rsp
    ret
END SYM(cgc_remainder)

ENTER SYM(cgc_log)
SYM(cgc_logl):
    fldt    (%rsp)
    fldln2
    fxch    %st(1)
    fyl2x
    ret
SYM(cgc_logf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fldln2
    fxch    %st(1)
    fyl2x
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_log):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fldln2
    fxch    %st(1)
    fyl2x
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_log)

ENTER SYM(cgc_log10)
SYM(cgc_log10l):
    fldt    (%rsp)
    fldlg2
    fxch    %st(1)
    fyl2x
    ret
SYM(cgc_log10f):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fldlg2
    fxch    %st(1)
    fyl2x
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_log10):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fldlg2
    fxch    %st(1)
    fyl2x
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_log10)

ENTER SYM(cgc_significand)
SYM(cgc_significandl):
    fldt    (%rsp)
    fxtract
    fstp    %st(1)
    ret
SYM(cgc_significandf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fxtract
    fstp    %st(1)
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_significand):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fxtract
    fstp    %st(1)
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_significand)

ENTER SYM(cgc_scalbn)
SYM(cgc_scalbnl):
    // long double in %rsp, int in %edi
    sub     $16, %rsp
    movl    %edi, 8(%rsp)
    fildl   8(%rsp)
    fldt    16(%rsp)
    add     $16, %rsp
    fscale
    fstp    %st(1)
    ret
SYM(cgc_scalbnf):
    // float in %xmm0, int in %edi
    sub     $16, %rsp
    movl    %edi, 8(%rsp)
    movss   %xmm0, (%rsp)
    fildl   8(%rsp)
    flds    (%rsp)
    fscale
    fstp    %st(1)
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $16, %rsp
    ret
SYM(cgc_scalbn):
    // double in %xmm0, int in %edi
    sub     $16, %rsp
    movl    %edi, 8(%rsp)
    movsd   %xmm0, (%rsp)
    fildl   8(%rsp)
    fldl    (%rsp)
    fscale
    fstp    %st(1)
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $16, %rsp
    ret
END SYM(cgc_scalbn)

ENTER SYM(cgc_scalbln)
SYM(cgc_scalblnl):
    jmp     SYM(cgc_scalbnl)
SYM(cgc_scalblnf):
    jmp     SYM(cgc_scalbnf)
SYM(cgc_scalbln):
    jmp     SYM(cgc_scalbn)
END SYM(cgc_scalbln)

ENTER SYM(cgc_rint)
SYM(cgc_rintl):
    fldt    (%rsp)
    frndint
    ret
SYM(cgc_rintf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    frndint
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_rint):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    frndint
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_rint)

ENTER SYM(cgc_sqrt)
SYM(cgc_sqrtl):
    fldt    (%rsp)
    fsqrt
    ret
SYM(cgc_sqrtf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fsqrt
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_sqrt):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fsqrt
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_sqrt)

ENTER SYM(cgc_fabs)
SYM(cgc_fabsl):
    fldt    (%rsp)
    fabs
    ret
SYM(cgc_fabsf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fabs
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_fabs):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fabs
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_fabs)

ENTER SYM(cgc_atan2)
SYM(cgc_atan2l):
    fldt    (%rsp)
    fldt    16(%rsp)
    fpatan
    ret
SYM(cgc_atan2f):
    sub     $16, %rsp
    movss   %xmm0, (%rsp)
    movss   %xmm1, 8(%rsp)
    flds    (%rsp)
    flds    8(%rsp)
    fpatan
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $16, %rsp
    ret
SYM(cgc_atan2):
    sub     $16, %rsp
    movsd   %xmm0, (%rsp)
    movsd   %xmm1, 8(%rsp)
    fldl    (%rsp)
    fldl    8(%rsp)
    fpatan
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $16, %rsp
    ret
END SYM(cgc_atan2)

ENTER SYM(cgc_log2)
SYM(cgc_log2l):
    fldt    (%rsp)
    fld1
    fxch
    fyl2x
    ret
SYM(cgc_log2f):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fld1
    fxch
    fyl2x
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
SYM(cgc_log2):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fld1
    fxch
    fyl2x
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_log2)

ENTER SYM(cgc_exp2)
    .type    SYM(cgc_exp2xf), @function
    .type    SYM(cgc_exp2x), @function
SYM(cgc_exp2l):
    fldt    (%rsp)
    fld     %st(0)
    frndint
    fsubr   %st,%st(1)
    fxch
    f2xm1
    fld1
    faddp
    fscale
    fstp    %st(1)
    ret
SYM(cgc_exp2f):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    add     $8, %rsp
    jmp     SYM(cgc_exp2xf)
SYM(cgc_exp2):
    sub     $16, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
SYM(cgc_exp2x):
    fld     %st(0)
    frndint
    fsubr   %st,%st(1)
    fxch
    f2xm1
    fld1
    faddp
    fscale
    fstp    %st(1)
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $16, %rsp
    ret
SYM(cgc_exp2xf):
    fld     %st(0)
    frndint
    fsubr   %st,%st(1)
    fxch
    f2xm1
    fld1
    faddp
    fscale
    fstp    %st(1)
    sub     $8, %rsp
    fstps   (%rsp)
    movss   (%rsp), %xmm0
    add     $8, %rsp
    ret
END SYM(cgc_exp2)
.size    SYM(cgc_exp2x), . - SYM(cgc_exp2x)
.size    SYM(cgc_exp2xf), . - SYM(cgc_exp2xf)

ENTER SYM(cgc_pow)
SYM(cgc_powl):
    fldt    16(%rsp)
    fldt    (%rsp)
    fyl2x
    fld     %st(0)
    frndint
    fsubr   %st,%st(1)
    fxch
    f2xm1
    fld1
    faddp
    fscale
    fstp    %st(1)
    ret
SYM(cgc_powf):
    sub     $16, %rsp
    movss   %xmm1, 8(%rsp)
    movss   %xmm0, (%rsp)
    flds    8(%rsp)
    flds    (%rsp)
    add     $16, %rsp
    fyl2x
    jmp     SYM(cgc_exp2xf)
SYM(cgc_pow):
    sub     $16, %rsp
    movsd   %xmm1, 8(%rsp)
    movsd   %xmm0, (%rsp)
    fldl    8(%rsp)
    fldl    (%rsp)
    fyl2x
    jmp     SYM(cgc_exp2x)
END SYM(cgc_pow)

ENTER SYM(cgc_exp)
SYM(cgc_expl):
    fldt    (%rsp)
    fldl2e
    fmulp
    fld     %st(0)
    frndint
    fsubr   %st,%st(1)
    fxch
    f2xm1
    fld1
    faddp
    fscale
    fstp    %st(1)
    ret
SYM(cgc_expf):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    add     $8, %rsp
    fldl2e
    fmulp
    jmp     SYM(cgc_exp2xf)
SYM(cgc_exp):
    sub     $16, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fldl2e
    fmulp
    jmp     SYM(cgc_exp2x)
END SYM(cgc_exp)

.global SYM(cgc_setjmp)
.type SYM(cgc_setjmp), @function
SYM(cgc_setjmp):
    // jmp_buf pointer is in %rdi
    movq    (%rsp), %rax        // return address
    movq    %rax, 0(%rdi)       // save return address
    movq    %rbx, 8(%rdi)
    movq    %rsp, 16(%rdi)
    movq    %rbp, 24(%rdi)
    movq    %r12, 32(%rdi)
    movq    %r13, 40(%rdi)
    movq    %r14, 48(%rdi)
    movq    %r15, 56(%rdi)
    xorl    %eax, %eax
    ret
.size SYM(cgc_setjmp), . - SYM(cgc_setjmp)

.global SYM(cgc_longjmp)
.type SYM(cgc_longjmp), @function
SYM(cgc_longjmp):
    // jmp_buf pointer in %rdi, value in %esi
    movl    %esi, %eax          // return value
    movq    0(%rdi), %rdx       // return address
    movq    8(%rdi), %rbx
    movq    16(%rdi), %rsp
    movq    24(%rdi), %rbp
    movq    32(%rdi), %r12
    movq    40(%rdi), %r13
    movq    48(%rdi), %r14
    movq    56(%rdi), %r15
    testl   %eax, %eax
    jnz     1f
    incl    %eax
1:
    movq    %rdx, (%rsp)       // restore return address
    ret
.size SYM(cgc_longjmp), . - SYM(cgc_longjmp)

#if defined(__linux__) && defined(__ELF__)
.section .note.GNU-stack,"",%progbits
#endif
