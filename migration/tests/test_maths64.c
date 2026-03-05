#include <stdio.h>
#include <math.h>
#include <stdlib.h>

// Declare the cgc_ math functions from maths64.S
// Double versions
extern double cgc_sin(double x);
extern double cgc_cos(double x);
extern double cgc_tan(double x);
extern double cgc_sqrt(double x);
extern double cgc_fabs(double x);
extern double cgc_atan2(double y, double x);
extern double cgc_log(double x);
extern double cgc_log10(double x);
extern double cgc_log2(double x);
extern double cgc_exp(double x);
extern double cgc_exp2(double x);
extern double cgc_pow(double x, double y);
extern double cgc_remainder(double x, double y);
extern double cgc_significand(double x);
extern double cgc_scalbn(double x, int n);
extern double cgc_rint(double x);

// Float versions - THESE WERE MISSING!
extern float cgc_sinf(float x);
extern float cgc_cosf(float x);
extern float cgc_tanf(float x);
extern float cgc_sqrtf(float x);
extern float cgc_fabsf(float x);
extern float cgc_atan2f(float y, float x);
extern float cgc_logf(float x);
extern float cgc_log10f(float x);
extern float cgc_log2f(float x);
extern float cgc_expf(float x);
extern float cgc_exp2f(float x);
extern float cgc_powf(float x, float y);
extern float cgc_remainderf(float x, float y);
extern float cgc_significandf(float x);
extern float cgc_scalbnf(float x, int n);
extern float cgc_rintf(float x);

#define TOLERANCE_DOUBLE 1e-9
#define TOLERANCE_FLOAT 1e-6
#define MAX(a,b) ((a) > (b) ? (a) : (b))

int test_count = 0;
int pass_count = 0;
int fail_count = 0;

void test_float(const char *name, float result, float expected) {
    test_count++;
    float diff = fabsf(result - expected);
    float relative_error = diff / MAX(fabsf(expected), 1.0f);

    if (relative_error < TOLERANCE_FLOAT || diff < TOLERANCE_FLOAT) {
        printf("[PASS] %s: %.9f (expected %.9f)\n", name, result, expected);
        pass_count++;
    } else {
        printf("[FAIL] %s: %.9f (expected %.9f, error: %.9e)\n",
               name, result, expected, diff);
        fail_count++;
    }
}

void test_double(const char *name, double result, double expected) {
    test_count++;
    double diff = fabs(result - expected);
    double relative_error = diff / MAX(fabs(expected), 1.0);

    if (relative_error < TOLERANCE_DOUBLE || diff < TOLERANCE_DOUBLE) {
        printf("[PASS] %s: %.15f (expected %.15f)\n", name, result, expected);
        pass_count++;
    } else {
        printf("[FAIL] %s: %.15f (expected %.15f, error: %.15e)\n",
               name, result, expected, diff);
        fail_count++;
    }
}

int main() {
    printf("=== Testing maths64.S functions ===\n\n");

    // Test sqrt
    printf("--- Testing cgc_sqrt (double) ---\n");
    test_double("sqrt(16.0)", cgc_sqrt(16.0), 4.0);
    test_double("sqrt(2.0)", cgc_sqrt(2.0), sqrt(2.0));
    test_double("sqrt(100.0)", cgc_sqrt(100.0), 10.0);
    test_double("sqrt(0.25)", cgc_sqrt(0.25), 0.5);
    printf("\n");

    printf("--- Testing cgc_sqrtf (float) ---\n");
    test_float("sqrtf(16.0f)", cgc_sqrtf(16.0f), 4.0f);
    test_float("sqrtf(2.0f)", cgc_sqrtf(2.0f), sqrtf(2.0f));
    test_float("sqrtf(100.0f)", cgc_sqrtf(100.0f), 10.0f);
    test_float("sqrtf(0.25f)", cgc_sqrtf(0.25f), 0.5f);
    printf("\n");

    // Test sin
    printf("--- Testing cgc_sin (double) ---\n");
    test_double("sin(0.0)", cgc_sin(0.0), 0.0);
    test_double("sin(π/2)", cgc_sin(M_PI/2.0), 1.0);
    test_double("sin(π)", cgc_sin(M_PI), 0.0);
    test_double("sin(π/6)", cgc_sin(M_PI/6.0), 0.5);
    test_double("sin(2π)", cgc_sin(2*M_PI), 0.0);
    printf("\n");

    printf("--- Testing cgc_sinf (float) ---\n");
    test_float("sinf(0.0f)", cgc_sinf(0.0f), 0.0f);
    test_float("sinf(π/2)", cgc_sinf((float)(M_PI/2.0)), 1.0f);
    test_float("sinf(π/6)", cgc_sinf((float)(M_PI/6.0)), 0.5f);
    printf("\n");

    // Test cos
    printf("--- Testing cgc_cos ---\n");
    test_double("cos(0.0)", cgc_cos(0.0), 1.0);
    test_double("cos(π)", cgc_cos(M_PI), -1.0);
    test_double("cos(π/2)", cgc_cos(M_PI/2.0), 0.0);
    test_double("cos(π/3)", cgc_cos(M_PI/3.0), 0.5);
    test_double("cos(2π)", cgc_cos(2*M_PI), 1.0);
    printf("\n");

    // Test tan
    printf("--- Testing cgc_tan ---\n");
    test_double("tan(0.0)", cgc_tan(0.0), 0.0);
    test_double("tan(π/4)", cgc_tan(M_PI/4.0), 1.0);
    test_double("tan(π)", cgc_tan(M_PI), 0.0);
    test_double("tan(-π/4)", cgc_tan(-M_PI/4.0), -1.0);
    printf("\n");

    // Test fabs
    printf("--- Testing cgc_fabs ---\n");
    test_double("fabs(5.0)", cgc_fabs(5.0), 5.0);
    test_double("fabs(-5.0)", cgc_fabs(-5.0), 5.0);
    test_double("fabs(0.0)", cgc_fabs(0.0), 0.0);
    test_double("fabs(-123.456)", cgc_fabs(-123.456), 123.456);
    printf("\n");

    // Test atan2
    printf("--- Testing cgc_atan2 ---\n");
    test_double("atan2(0.0, 1.0)", cgc_atan2(0.0, 1.0), 0.0);
    test_double("atan2(1.0, 0.0)", cgc_atan2(1.0, 0.0), M_PI/2.0);
    test_double("atan2(1.0, 1.0)", cgc_atan2(1.0, 1.0), M_PI/4.0);
    test_double("atan2(-1.0, -1.0)", cgc_atan2(-1.0, -1.0), -3.0*M_PI/4.0);
    printf("\n");

    // Test log (natural logarithm)
    printf("--- Testing cgc_log ---\n");
    test_double("log(1.0)", cgc_log(1.0), 0.0);
    test_double("log(e)", cgc_log(M_E), 1.0);
    test_double("log(e²)", cgc_log(M_E*M_E), 2.0);
    test_double("log(10.0)", cgc_log(10.0), log(10.0));
    printf("\n");

    // Test log10
    printf("--- Testing cgc_log10 ---\n");
    test_double("log10(1.0)", cgc_log10(1.0), 0.0);
    test_double("log10(10.0)", cgc_log10(10.0), 1.0);
    test_double("log10(100.0)", cgc_log10(100.0), 2.0);
    test_double("log10(1000.0)", cgc_log10(1000.0), 3.0);
    printf("\n");

    // Test log2
    printf("--- Testing cgc_log2 (double) ---\n");
    test_double("log2(1.0)", cgc_log2(1.0), 0.0);
    test_double("log2(2.0)", cgc_log2(2.0), 1.0);
    test_double("log2(8.0)", cgc_log2(8.0), 3.0);
    test_double("log2(1024.0)", cgc_log2(1024.0), 10.0);
    printf("\n");

    printf("--- Testing cgc_log2f (float) - CRITICAL (used in Childs_Game) ---\n");
    test_float("log2f(1.0f)", cgc_log2f(1.0f), 0.0f);
    test_float("log2f(2.0f)", cgc_log2f(2.0f), 1.0f);
    test_float("log2f(8.0f)", cgc_log2f(8.0f), 3.0f);
    test_float("log2f(16.0f)", cgc_log2f(16.0f), 4.0f);
    test_float("log2f(65536.0f)", cgc_log2f(65536.0f), 16.0f);  // UPPER_RAND_MAX+1
    printf("\n");

    // Test exp
    printf("--- Testing cgc_exp ---\n");
    test_double("exp(0.0)", cgc_exp(0.0), 1.0);
    test_double("exp(1.0)", cgc_exp(1.0), M_E);
    test_double("exp(2.0)", cgc_exp(2.0), exp(2.0));
    test_double("exp(-1.0)", cgc_exp(-1.0), 1.0/M_E);
    printf("\n");

    // Test exp2
    printf("--- Testing cgc_exp2 ---\n");
    test_double("exp2(0.0)", cgc_exp2(0.0), 1.0);
    test_double("exp2(1.0)", cgc_exp2(1.0), 2.0);
    test_double("exp2(3.0)", cgc_exp2(3.0), 8.0);
    test_double("exp2(10.0)", cgc_exp2(10.0), 1024.0);
    test_double("exp2(-1.0)", cgc_exp2(-1.0), 0.5);
    printf("\n");

    // Test pow
    printf("--- Testing cgc_pow ---\n");
    test_double("pow(2.0, 3.0)", cgc_pow(2.0, 3.0), 8.0);
    test_double("pow(10.0, 2.0)", cgc_pow(10.0, 2.0), 100.0);
    test_double("pow(5.0, 0.0)", cgc_pow(5.0, 0.0), 1.0);
    test_double("pow(2.0, -2.0)", cgc_pow(2.0, -2.0), 0.25);
    test_double("pow(9.0, 0.5)", cgc_pow(9.0, 0.5), 3.0);
    printf("\n");

    // Test remainder
    printf("--- Testing cgc_remainder ---\n");
    test_double("remainder(5.0, 2.0)", cgc_remainder(5.0, 2.0), remainder(5.0, 2.0));
    test_double("remainder(7.5, 2.5)", cgc_remainder(7.5, 2.5), remainder(7.5, 2.5));
    test_double("remainder(10.0, 3.0)", cgc_remainder(10.0, 3.0), remainder(10.0, 3.0));
    printf("\n");

    // Test significand (extracts mantissa)
    printf("--- Testing cgc_significand ---\n");
    test_double("significand(8.0)", cgc_significand(8.0), significand(8.0));
    test_double("significand(16.0)", cgc_significand(16.0), significand(16.0));
    test_double("significand(3.14)", cgc_significand(3.14), significand(3.14));
    printf("\n");

    // Test scalbn (x * 2^n)
    printf("--- Testing cgc_scalbn ---\n");
    test_double("scalbn(1.5, 3)", cgc_scalbn(1.5, 3), 12.0);  // 1.5 * 2^3 = 12
    test_double("scalbn(2.0, 4)", cgc_scalbn(2.0, 4), 32.0);  // 2.0 * 2^4 = 32
    test_double("scalbn(5.0, -2)", cgc_scalbn(5.0, -2), 1.25); // 5.0 * 2^-2 = 1.25
    test_double("scalbn(1.0, 0)", cgc_scalbn(1.0, 0), 1.0);
    printf("\n");

    // Test rint (round to nearest integer)
    printf("--- Testing cgc_rint ---\n");
    test_double("rint(2.3)", cgc_rint(2.3), 2.0);
    test_double("rint(2.7)", cgc_rint(2.7), 3.0);
    test_double("rint(-3.2)", cgc_rint(-3.2), -3.0);
    test_double("rint(-3.8)", cgc_rint(-3.8), -4.0);
    test_double("rint(5.0)", cgc_rint(5.0), 5.0);
    printf("\n");

    // Summary
    printf("=== Test Summary ===\n");
    printf("Total tests: %d\n", test_count);
    printf("Passed: %d\n", pass_count);
    printf("Failed: %d\n", fail_count);

    if (fail_count == 0) {
        printf("\n✓ All tests passed!\n");
        return 0;
    } else {
        printf("\n✗ %d test(s) failed\n", fail_count);
        return 1;
    }
}
