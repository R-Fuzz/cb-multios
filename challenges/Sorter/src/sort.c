/*
 * Copyright (c) 2015 Kaprica Security, Inc.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 */
#ifdef __x86_64__
#include "cgc_stdlib.h"
#include "cgc_stdint.h"

/* On 64-bit, fptrs is intptr_t * to hold full-width function pointers */
#define MALLOC64(_FPTRS, _SZ) ((*((void *(*)(cgc_size_t))((_FPTRS)[0])))(((_SZ))))
#define FREE64(_FPTRS, _PTR)  ((*((void *(*)(void *))((_FPTRS)[1])))(((_PTR))))
#define MEMCPY64(_FPTRS, _DST, _SRC, _SZ) ((*(void *(*)(void *, void *, cgc_size_t))((_FPTRS)[2]))((_DST), (_SRC), (_SZ)))
#define MEMMOVE64(_FPTRS, _DST, _SRC, _SZ) ((*(void *(*)(void *, void *, cgc_size_t))((_FPTRS)[3]))((_DST), (_SRC), (_SZ)))
#define PRINT_ARRAY64(_FPTRS, _ARR, _SZ) ((*(void (*)(int *, cgc_size_t))((_FPTRS)[4]))((_ARR), (_SZ)))
#define SWAP64(_FPTRS, _FIRST, _SECOND) ((*(void (*)(int *, int *))((_FPTRS)[5]))((_FIRST), (_SECOND)))
#define HEAPIFY64(_FPTRS, _ARR, _SZ) ((*(int (*)(int *, cgc_size_t, intptr_t *))((_FPTRS)[6]))((_ARR), (_SZ), (_FPTRS)))
#define HEAP_PROPAGATE64(_FPTRS, _ARR, _SZ, _SWAP_IDX) \
                            ((*(int (*)(int *, cgc_size_t, cgc_size_t, intptr_t *))((_FPTRS)[7]))((_ARR), (_SZ), (_SWAP_IDX), (_FPTRS)))
#define MERGE_HELPER64(_FPTRS, _ARR1, _ARR2, _IDX1, _IDX2) \
                            ((*(int (*)(int *, int *, int, int, intptr_t *))((_FPTRS)[8]))((_ARR1), (_ARR2), (_IDX1), (_IDX2), (_FPTRS)))
#define ALLOCATE64(_FPTRS, _LEN, _IS_X, _PADDR) ((*(int (*)(cgc_size_t, int, void **))((_FPTRS)[9]))((_LEN), (_IS_X), (_PADDR)))
#define DEALLOCATE64(_FPTRS, _ADDR, _LEN) ((*(int (*)(void *, cgc_size_t))((_FPTRS)[10]))((_ADDR), (_LEN)))

int insertion_sort(int *array, cgc_size_t array_size, intptr_t *fptrs)
{
    int num_comparisons = 0;
    int *sorted_array = MALLOC64(fptrs, sizeof(int) * array_size);
    MEMCPY64(fptrs, sorted_array, array, sizeof(int) * array_size);
    for (int i = 0; i < (int)array_size; i++) {
        int j = 0;
        int temp = sorted_array[i];
        for (j = i+1; j < (int)array_size; j++) {
            ++num_comparisons;
            if (temp > sorted_array[j]) {
                temp = sorted_array[j];
                MEMMOVE64(fptrs, &sorted_array[i+1], &sorted_array[i], sizeof(int) * (j-i));
                sorted_array[i] = temp;
            }
        }
    }

    PRINT_ARRAY64(fptrs, sorted_array, array_size);
    FREE64(fptrs, sorted_array);
    return num_comparisons;
}

int selection_sort(int *array, cgc_size_t array_size, intptr_t *fptrs)
{
    int num_comparisons = 0;
    int *sorted_array = MALLOC64(fptrs, sizeof(int) * array_size);
    sorted_array = MEMCPY64(fptrs, sorted_array, array, sizeof(int) * array_size);
    for (int i = 0; i < (int)array_size; i++) {
        int j = 0;
        int z = i;
        int temp = sorted_array[i];
        for (j = i+1; j < (int)array_size; j++) {
            ++num_comparisons;
            if (temp > sorted_array[j]) {
                temp = sorted_array[j];
                z = j;
            }
        }
        ++num_comparisons;
        if (z != i) {
            sorted_array[z] = sorted_array[i];
            sorted_array[i] = temp;
        }
    }

    PRINT_ARRAY64(fptrs, sorted_array, array_size);
    FREE64(fptrs, sorted_array);
    return num_comparisons;
}

int heap_propagate(int *array, cgc_size_t array_size, cgc_size_t swap_idx, intptr_t *fptrs)
{
    int num_comparisons = 0;
    int parent, lchild, rchild;

    while (1) {
        parent = array[swap_idx];
        ++num_comparisons;
        if ((2*swap_idx + 1) < array_size) {
            lchild = array[2*swap_idx + 1];
        } else {
            break;
        }

        ++num_comparisons;
        if ((2*swap_idx + 2) < array_size) {
            rchild = array[2*swap_idx + 2];
        } else {
            ++num_comparisons;
            if (parent <  lchild) {
                SWAP64(fptrs, &array[2*swap_idx + 1], &array[swap_idx]);
                swap_idx = 2*swap_idx + 1;
            }
            break;
        }

        ++num_comparisons;
        if (lchild >= rchild) {
            ++num_comparisons;
            if (parent < lchild) {
                SWAP64(fptrs, &array[2*swap_idx + 1], &array[swap_idx]);
                swap_idx = 2*swap_idx + 1;
            } else {
                break;
            }
        } else {
            ++num_comparisons;
            if (parent < rchild) {
                SWAP64(fptrs, &array[2*swap_idx + 2], &array[swap_idx]);
                swap_idx = 2*swap_idx + 2;
            } else {
                break;
            }
        }
    }

    return num_comparisons;
}

int heapify(int *array, cgc_size_t array_size, intptr_t *fptrs)
{
    int num_comparisons = 0;
    if (array_size < 2)
        return 1;

    int parent = 0;
    int lchild = 0;
    int rchild = 0;
    int ridx = array_size - 1;

    if (ridx == 1) {
        if (array[0] < array[1]) {
            SWAP64(fptrs, &array[0], &array[1]);
        }
        return 1;
    }

    if (array_size % 2 == 0) {
        lchild = array[ridx];
        parent = array[(ridx - 1) / 2];
        if (parent < lchild)
            SWAP64(fptrs, &array[ridx], &array[(ridx - 1) / 2]);
        --ridx;
    }

    int done = 0;
    while (!done) {
        int swap_idx = 0;
        rchild = array[ridx];
        lchild = array[ridx - 1];
        parent = array[(ridx - 1) / 2];

        ++num_comparisons;
        if (lchild > rchild) {
            ++num_comparisons;
            if (parent < lchild)
                swap_idx = ridx - 1;
        } else {
            ++num_comparisons;
            if (parent < rchild)
                swap_idx = ridx;
        }

        if (swap_idx) {
            SWAP64(fptrs, &array[(ridx - 1) / 2], &array[swap_idx]);
            num_comparisons += HEAP_PROPAGATE64(fptrs, array, array_size, swap_idx);
        }

        if (!((ridx - 1) / 2))
            done = 1;

        ridx -= 2;
    }

    return num_comparisons;
}

int heap_sort(int *array, cgc_size_t array_size, intptr_t *fptrs)
{
    int num_comparisons = 0;
    int real_array_size = array_size;
    int *sorted_array = MALLOC64(fptrs, sizeof(int) * array_size);
    MEMCPY64(fptrs, sorted_array, array, sizeof(int) * array_size);
    num_comparisons += HEAPIFY64(fptrs, sorted_array, array_size);
    while (array_size) {
        SWAP64(fptrs, &sorted_array[0], &sorted_array[array_size - 1]);
        num_comparisons += HEAP_PROPAGATE64(fptrs, sorted_array, --array_size, 0);
    }
    array_size = real_array_size;

    PRINT_ARRAY64(fptrs, sorted_array, array_size);
    FREE64(fptrs, sorted_array);
    return num_comparisons;
}

int merge_helper(int *array, int *temp_array, int idx_start, int idx_end, intptr_t *fptrs)
{
    if (idx_end - idx_start < 2)
        return 1;

    int idx_mid = (idx_end + idx_start) / 2;
    int num_comparisons = 0;
    num_comparisons += MERGE_HELPER64(fptrs, array, temp_array, idx_start, idx_mid);
    num_comparisons += MERGE_HELPER64(fptrs, array, temp_array, idx_mid, idx_end);

    int i = 0;
    int idx_left = idx_start;
    int idx_right = idx_mid;

    for (i = idx_start; i < idx_end; i++) {
        ++num_comparisons;
        if (idx_left < idx_mid) {
            ++num_comparisons;
            if (idx_right >= idx_end || array[idx_left] <= array[idx_right])
                temp_array[i] = array[idx_left++];
            else
                temp_array[i] = array[idx_right++];
        } else {
            temp_array[i] = array[idx_right++];
        }
    }
    MEMCPY64(fptrs, &array[idx_start], &temp_array[idx_start], (idx_end - idx_start) * sizeof(int));

    return num_comparisons;
}

int merge_sort(int *array, cgc_size_t array_size, intptr_t *fptrs)
{
    int *orig_array = NULL;
    int used_allocate = 0;
    int *temp_array = MALLOC64(fptrs, sizeof(int) * array_size);

#ifdef PATCHED_1
    if (array_size <= 1024 && ALLOCATE64(fptrs, 4096, 0, (void **)&orig_array) == 0)
#else
    if (array_size <= 1048 && ALLOCATE64(fptrs, 4096, 0, (void **)&orig_array) == 0)
#endif
        used_allocate = 1;
    else
        orig_array = MALLOC64(fptrs, sizeof(int) * array_size);
    MEMCPY64(fptrs, orig_array, array, sizeof(int) * array_size);
    int num_comparisons = MERGE_HELPER64(fptrs, array, temp_array, 0, array_size);
    PRINT_ARRAY64(fptrs, array, array_size);
    MEMCPY64(fptrs, array, orig_array, sizeof(int) * array_size);
    FREE64(fptrs, temp_array);
    if (used_allocate)
        DEALLOCATE64(fptrs, orig_array, 4096);
    else
        FREE64(fptrs, orig_array);
    return num_comparisons;
}
#endif /* __x86_64__ */

//int insertion_sort(int *array, cgc_size_t array_size, int *fptrs)
//{
//    int num_comparisons = 0;
//    int *sorted_array = MALLOC(fptrs, sizeof(int) * array_size);
//    MEMCPY(fptrs, sorted_array, array, sizeof(int) * array_size);
//    for (int i = 0; i < array_size; i++) {
//        int j = 0;
//        int temp = sorted_array[i];
//        for (j = i+1; j < array_size; j++) {
//            ++num_comparisons;
//            if (temp > sorted_array[j]) {
//                temp = sorted_array[j];
//                cgc_memmove(fptrs, &sorted_array[i+1], &sorted_array[i], sizeof(int) * (j-i));
//                sorted_array[i] = temp;
//            }
//        }
//    }
//
//    PRINT_ARRAY(fptrs, sorted_array, array_size);
//    FREE(fptrs, sorted_array);
//    return num_comparisons;
//}
//
//int selection_sort(int *array, cgc_size_t array_size, int *fptrs)
//{
//    int num_comparisons = 0;
//    int *sorted_array = MALLOC(fptrs, sizeof(int) * array_size);
//    sorted_array = MEMCPY(fptrs, sorted_array, array, sizeof(int) * array_size);
//    for (int i = 0; i < array_size; i++) {
//        int j = 0;
//        int z = i;
//        int temp = sorted_array[i];
//        for (j = i+1; j < array_size; j++) {
//            ++num_comparisons;
//            if (temp > sorted_array[j]) {
//                temp = sorted_array[j];
//                z = j;
//            }
//        }
//        ++num_comparisons;
//        if (z != i) {
//            sorted_array[z] = sorted_array[i];
//            sorted_array[i] = temp;
//        }
//    }
//
//    PRINT_ARRAY(fptrs, sorted_array, array_size);
//    FREE(fptrs, sorted_array);
//    return num_comparisons;
//}
//
//int heap_propagate(int *array, cgc_size_t array_size, cgc_size_t swap_idx, int *fptrs)
//{
//    int num_comparisons = 0;
//    int parent, lchild, rchild;
//
//    while (1) {
//        parent = array[swap_idx];
//        ++num_comparisons;
//        if ((2*swap_idx + 1) < array_size) {
//            lchild = array[2*swap_idx + 1];
//        } else {
//            break;
//        }
//
//        ++num_comparisons;
//        if ((2*swap_idx + 2) < array_size) {
//            rchild = array[2*swap_idx + 2];
//        } else {
//            ++num_comparisons;
//            if (parent <  lchild) {
//                SWAP(fptrs, &array[2*swap_idx + 1], &array[swap_idx]);
//                swap_idx = 2*swap_idx + 1;
//            }
//            break;
//        }
//
//        ++num_comparisons;
//        if (lchild >= rchild) {
//            ++num_comparisons;
//            if (parent < lchild) {
//                SWAP(fptrs, &array[2*swap_idx + 1], &array[swap_idx]);
//                swap_idx = 2*swap_idx + 1;
//            } else {
//                break;
//            }
//        } else {
//            ++num_comparisons;
//            if (parent < rchild) {
//                SWAP(fptrs, &array[2*swap_idx + 2], &array[swap_idx]);
//                swap_idx = 2*swap_idx + 2;
//            } else {
//                break;
//            }
//        }
//    }
//
//    return num_comparisons;
//}
//
//int heapify(int *array, cgc_size_t array_size, int *fptrs)
//{
//    int num_comparisons = 0;
//    if (array_size < 2)
//        return 1;
//
//    int parent = 0;
//    int lchild = 0;
//    int rchild = 0;
//    int ridx = array_size - 1;
//
//    if (ridx == 1) {
//        if (array[0] < array[1]) {
//            SWAP(fptrs, &array[0], &array[1]);
//        }
//        return 1;
//    }
//
//    if (array_size % 2 == 0) {
//        lchild = array[ridx];
//        parent = array[(ridx - 1) / 2];
//        if (parent < lchild)
//            SWAP(fptrs, &array[ridx], &array[(ridx - 1) / 2]);
//        --ridx;
//    }
//
//    int done = 0;
//    while (!done) {
//        int swap_idx = 0;
//        rchild = array[ridx];
//        lchild = array[ridx - 1];
//        parent = array[(ridx - 1) / 2];
//
//        ++num_comparisons;
//        if (lchild > rchild) {
//            ++num_comparisons;
//            if (parent < lchild)
//                swap_idx = ridx - 1;
//        } else {
//            ++num_comparisons;
//            if (parent < rchild)
//                swap_idx = ridx;
//        }
//
//        if (swap_idx) {
//            SWAP(fptrs, &array[(ridx - 1) / 2], &array[swap_idx]);
//            num_comparisons += HEAP_PROPAGATE(fptrs, array, array_size, swap_idx);
//        }
//
//        if (!((ridx - 1) / 2))
//            done = 1;
//
//        ridx -= 2;
//    }
//
//    return num_comparisons;
//}
//
//int heap_sort(int *array, cgc_size_t array_size, int *fptrs)
//{
//    int num_comparisons = 0;
//    int real_array_size = array_size;
//    int *sorted_array = MALLOC(fptrs, sizeof(int) * array_size);
//    MEMCPY(fptrs, sorted_array, array, sizeof(int) * array_size);
//    num_comparisons += HEAPIFY(fptrs, sorted_array, array_size);
//    while (array_size) {
//        SWAP(fptrs, &sorted_array[0], &sorted_array[array_size - 1]);
//        num_comparisons += HEAP_PROPAGATE(fptrs, sorted_array, --array_size, 0);
//    }
//    array_size = real_array_size;
//
//    PRINT_ARRAY(fptrs, sorted_array, array_size);
//    FREE(fptrs, sorted_array);
//    return num_comparisons;
//}
//
//int merge_helper(int *array, int *temp_array, int idx_start, int idx_end, int *fptrs)
//{
//    if (idx_end - idx_start < 2)
//        return 1;
//
//    int idx_mid = (idx_end + idx_start) / 2;
//    int num_comparisons = 0;
//    num_comparisons += MERGE_HELPER(fptrs, array, temp_array, idx_start, idx_mid);
//    num_comparisons += MERGE_HELPER(fptrs, array, temp_array, idx_mid, idx_end);
//
//    int i = 0;
//    int idx_left = idx_start;
//    int idx_right = idx_mid;
//
//    for (i = idx_start; i < idx_end; i++) {
//        ++num_comparisons;
//        if (idx_left < idx_mid) {
//            ++num_comparisons;
//            if (idx_right >= idx_end || array[idx_left] <= array[idx_right])
//                temp_array[i] = array[idx_left++];
//            else
//                temp_array[i] = array[idx_right++];
//        } else {
//            temp_array[i] = array[idx_right++];
//        }
//    }
//    MEMCPY(fptrs, &array[idx_start], &temp_array[idx_start], (idx_end - idx_start) * sizeof(int));
//
//    return num_comparisons;
//}
//
//int merge_sort(int *array, cgc_size_t array_size, int *fptrs)
//{
//    int *orig_array = NULL;
//    int used_allocate = 0;
//    int *temp_array = MALLOC(fptrs, sizeof(int) * array_size);
//
//
//#ifdef PATCHED_1
//    if (array_size <= 1024 && cgc_ALLOCATE(fptrs, 4096, 0, (void **)&orig_array) == 0)
//#else
//    if (array_size <= 1048 && cgc_ALLOCATE(fptrs, 4096, 0, (void **)&orig_array) == 0)
//        used_allocate = 1;
//    else
//        orig_array = MALLOC(fptrs, sizeof(int) * array_size);
//    MEMCPY(fptrs, orig_array, array, sizeof(int) * array_size);
//    int num_comparisons = MERGE_HELPER(fptrs, array, temp_array, 0, array_size);
//    PRINT_ARRAY(fptrs, array, array_size);
//    MEMCPY(fptrs, array, orig_array, sizeof(int) * array_size);
//    FREE(fptrs, temp_array);
//    if (used_allocate)
//        DEALLOCATE(fptrs, orig_array, 4096);
//    else
//        FREE(fptrs, orig_array);
//    return num_comparisons;
//}
