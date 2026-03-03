/*

Author: James Connor (jymbo@cromulence.co)

Copyright (c) 2014 Cromulence LLC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

*/
#include "libcgc.h"
#include "cgc_stdarg.h"
#include "cgc_stdlib.h"
#include "cgc_stdint.h"
#include "cgc_mymath.h"
#include "cgc_service.h"
#include "cgc_llist.h"

#include "cgc_map.h"
#include "cgc_ui.h"


/*
graph traversal service that emulates a street map.  
provides routing from point to point 
map can be created/edited by adding streets, intersections, 
and addresses
*/


int main(int cgc_argc, char *cgc_argv[]){
	//new
	psList turnList = cgc_init_turnList();
	pmap thisMap = cgc_init_map("Newville");
	cgc_puts("This is Mapper.");
	cgc_prompt_loop(thisMap, turnList);

	/* Consume the extra 0\n sent by the test generator after exit.
	 * The poll generator's finish() node is always called at walk() end,
	 * but may also be invoked via graph edge traversal, causing it to
	 * execute twice and send two 0\n inputs. The prompt loop only reads
	 * one; drain the second here to prevent a broken pipe write failure. */
	{
		char drain[4];
		cgc_size_t rx;
		cgc_receive(STDIN, drain, sizeof(drain), &rx);
	}

	return 1;
}
