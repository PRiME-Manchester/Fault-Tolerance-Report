/****a* heat_demo.c/heat_demo_summary
*
* SUMMARY
*  a very, very simple 2D Heat equation SpiNNaker application
*  one core does one point!
*
* AUTHOR
*  Luis Plana - luis.plana@manchester.ac.uk
*
* DETAILS
*  Created on       : 27 Jul 2011
*  Version          : $Revision: 2531 $
*  Last modified on : $Date: 2013-08-20 12:34:21 +0100 (Tue, 20 Aug 2013) $
*  Last modified by : $Author: plana $
*  $Id: heat_demo.c 2531 2013-08-20 11:34:21Z plana $
*  $HeadURL: https://solem.cs.man.ac.uk/svn/demos/heat_demo/heat_demo.c $
*
* COPYRIGHT
*  Copyright (c) The University of Manchester, 2011. All rights reserved.
*  SpiNNaker Project
*  Advanced Processor Technologies Group
*  School of Computer Science
*
*******/

// SpiNNaker API
#include "spin1_api.h"


// ------------------------------------------------------------------------
// OPTIONS
// ------------------------------------------------------------------------
#define JTAG_INIT          TRUE
#define DUMP_CHK           TRUE


// ------------------------------------------------------------------------
// DEBUG parameters
// ------------------------------------------------------------------------
//#define DEBUG              TRUE
#define DEBUG_KEYS         500

#define VERBOSE            TRUE

// the visualiser has a bug with negative temperatures!
#define POSITIVE_TEMP      TRUE

// ------------------------------------------------------------------------
// core map choice
// ------------------------------------------------------------------------
#define MAP_2x2_on_4       TRUE
//#define MAP_5x4_on_48      TRUE
//#define MAP_12x12_on_144   TRUE
//#define MAP_24x12_on_288   TRUE
//#define MAP_24x24_on_576   TRUE
//#define MAP_48x24_on_1152  TRUE
//#define MAP_384x240_on_92160  TRUE

#ifdef MAP_2x2_on_4
  #define NUMBER_OF_XCHIPS 2
  #define NUMBER_OF_YCHIPS 2
  #define BOARD_XCHIPS 2
  #define BOARD_YCHIPS 2

  #define SEND_ALTERNATE   FALSE

//  #define TIMER_TICK_PERIOD  1000
//  #define TIMER_TICK_PERIOD  1500
  #define TIMER_TICK_PERIOD  2500
//  #define TIMER_TICK_PERIOD  25000
#endif

#ifdef MAP_5x4_on_48
  #define NUMBER_OF_XCHIPS 5
  #define NUMBER_OF_YCHIPS 4
  #define BOARD_XCHIPS 8
  #define BOARD_YCHIPS 8

  #define SEND_ALTERNATE   FALSE

//  #define TIMER_TICK_PERIOD  1000
  #define TIMER_TICK_PERIOD  1500
//  #define TIMER_TICK_PERIOD  2500
//  #define TIMER_TICK_PERIOD  25000
#endif

#ifdef MAP_12x12_on_144
  #define NUMBER_OF_XCHIPS 12
  #define NUMBER_OF_YCHIPS 12
  #define BOARD_XCHIPS 8
  #define BOARD_YCHIPS 8

  #define SEND_ALTERNATE   TRUE

//  #define TIMER_TICK_PERIOD  1000
  #define TIMER_TICK_PERIOD  1500
//  #define TIMER_TICK_PERIOD  2500
//  #define TIMER_TICK_PERIOD  25000
#endif

#ifdef MAP_24x12_on_288
  #define NUMBER_OF_XCHIPS 24
  #define NUMBER_OF_YCHIPS 12
  #define BOARD_XCHIPS 8
  #define BOARD_YCHIPS 8

  #define SEND_ALTERNATE   TRUE

//  #define TIMER_TICK_PERIOD  1000
  #define TIMER_TICK_PERIOD  1500
//  #define TIMER_TICK_PERIOD  2500
//  #define TIMER_TICK_PERIOD  25000
#endif

#ifdef MAP_24x24_on_576
  #define NUMBER_OF_XCHIPS 24
  #define NUMBER_OF_YCHIPS 24
  #define BOARD_XCHIPS 8
  #define BOARD_YCHIPS 8

  #define SEND_ALTERNATE   TRUE

//  #define TIMER_TICK_PERIOD  1000
  #define TIMER_TICK_PERIOD  1500
//  #define TIMER_TICK_PERIOD  2500
//  #define TIMER_TICK_PERIOD  25000
#endif

#ifdef MAP_48x24_on_1152
  #define NUMBER_OF_XCHIPS 48
  #define NUMBER_OF_YCHIPS 24
  #define BOARD_XCHIPS 8
  #define BOARD_YCHIPS 8

  #define SEND_ALTERNATE   TRUE

  #define TIMER_TICK_PERIOD  1000
//  #define TIMER_TICK_PERIOD  1500
//  #define TIMER_TICK_PERIOD  2500
//  #define TIMER_TICK_PERIOD  25000
#endif

#ifdef MAP_384x240_on_92160
  #define NUMBER_OF_XCHIPS 96
  #define NUMBER_OF_YCHIPS 60
  #define BOARD_XCHIPS 8
  #define BOARD_YCHIPS 8

  #define SEND_ALTERNATE   TRUE

  #define TIMER_TICK_PERIOD  1000
//  #define TIMER_TICK_PERIOD  1500
//  #define TIMER_TICK_PERIOD  2500
//  #define TIMER_TICK_PERIOD  25000
#endif


// ------------------------------------------------------------------------
// simulation parameters
// ------------------------------------------------------------------------
#define PARAM_CX           0.03125
#define PARAM_CY           0.03125

#define NORTH_INIT         (40 * 65536)
#define EAST_INIT          (10 * 65536)
#define SOUTH_INIT         (10 * 65536)
#define WEST_INIT          (40 * 65536)


// ------------------------------------------------------------------------
// Router definitions related to dumped packets
// ------------------------------------------------------------------------
#define RTR_DENABLE_BIT    2
#define RTR_DROUTE_MASK    0x00ffffc0  // leave links untouched!
#define PKT_TYPE_MC        0x00000000
#define RTR_TYPE_MASK      0x00c00000

#define RTR_DUMP_CNT       20


// ------------------------------------------------------------------------
// jtag definitions
// ------------------------------------------------------------------------
#define JTAG_NTRST	(1 << 27)
#define JTAG_TMS	(1 << 26)
#define JTAG_TDI	(1 << 25)
#define JTAG_TCK	(1 << 24)

#define JTAG_RTCK	(1 << 20)
#define JTAG_TDO	(1 << 19)
#define JTAG_INT	(1 << 15)


// ------------------------------------------------------------------------
// Routing table constants and macro definitions
// ------------------------------------------------------------------------
#define DONT_ROUTE_KEY     0xffff
#define KEY_CORE_MASK          0x0000001f
#define ROUTING_KEY(chip, core)    ((chip << 5) | core)
#define ROUTE_TO_CORE(core)        (1 << (core + 6))

#define NORTH              3
#define SOUTH              2
#define EAST               1
#define WEST               0

#define NORTH_ARRIVED      (1 << NORTH)
#define SOUTH_ARRIVED      (1 << SOUTH)
#define EAST_ARRIVED       (1 << EAST)
#define WEST_ARRIVED       (1 << WEST)
#define NONE_ARRIVED       0
#define NS_ARRIVED         (NORTH_ARRIVED | SOUTH_ARRIVED)
#define EW_ARRIVED         (EAST_ARRIVED | WEST_ARRIVED)
#define ALL_ARRIVED        (NS_ARRIVED | EW_ARRIVED)

#define CORE_TO_NORTH(core)        (core + 1)
#define CORE_TO_SOUTH(core)        (core - 1)
#define CORE_TO_EAST(core)         (core + 4)
#define CORE_TO_WEST(core)         (core - 4)

#define IS_NORTHERNMOST_CORE(core) (((core - 1) & 0x3) == 0x3)
#define IS_SOUTHERNMOST_CORE(core) (((core - 1) & 0x3) == 0x0)
#define IS_EASTERNMOST_CORE(core)  (((core - 1) & 0xc) == 0xc)
#define IS_WESTERNMOST_CORE(core)  (((core - 1) & 0xc) == 0x0)

#define NORTHERNMOST_CORE(core)    (((core - 1) | 0x3) + 1)
#define SOUTHERNMOST_CORE(core)    (((core - 1) & 0xc) + 1)
#define EASTERNMOST_CORE(core)     (((core - 1) | 0xc) + 1)
#define WESTERNMOST_CORE(core)     (((core - 1) & 0x3) + 1)

#define ROUTE_TO_LINK(link)        (1 << link)
#define EAST_LINK                  0
#define NORTH_EAST_LINK            1
#define NORTH_LINK                 2
#define WEST_LINK                  3
#define SOUTH_WEST_LINK            4
#define SOUTH_LINK                 5

#define CHIP_TO_NORTH(chip)     (chip + 1)
#define CHIP_TO_SOUTH(chip)     (chip - 1)
#define CHIP_TO_EAST(chip)      (chip + (1 << 8))
#define CHIP_TO_WEST(chip)      (chip - (1 << 8))

#define IS_NORTHERNMOST_CHIP(x, y) (y == (NUMBER_OF_YCHIPS - 1))
#define IS_SOUTHERNMOST_CHIP(x, y) (y == 0)
#define IS_EASTERNMOST_CHIP(x, y)  (x == (NUMBER_OF_XCHIPS - 1))
#define IS_WESTERNMOST_CHIP(x, y)  (x == 0)

#define IS_BORDER_CHIP(x, y) ((y == (NUMBER_OF_YCHIPS - 1)) || (y == 0) || (x == (NUMBER_OF_XCHIPS - 1)) || (x == 0))

#define CMD_MASK       0x0000001f
#define TEMP_MASK      0x0000001f

// use core 17 keys to distribute commands
#define CMD_KEY        ROUTING_KEY(0, 17)
#define STOP_KEY       ROUTING_KEY(0, 17)
#define PAUSE_KEY      ROUTING_KEY(1, 17)
#define RESUME_KEY     ROUTING_KEY(2, 17)

// use core 18 keys to distribute temperatures
#define TEMP_KEY       ROUTING_KEY(0, 18)
#define TEMP_NORTH_KEY ROUTING_KEY(16, 18)
#define TEMP_EAST_KEY  ROUTING_KEY(17, 18)
#define TEMP_SOUTH_KEY ROUTING_KEY(18, 18)
#define TEMP_WEST_KEY  ROUTING_KEY(19, 18)

// use core 19 keys for alternate command distribution
#define ALT_CMD_KEY        ROUTING_KEY(0, 19)
#define ALT_STOP_KEY       ROUTING_KEY(0, 19)
#define ALT_PAUSE_KEY      ROUTING_KEY(1, 19)
#define ALT_RESUME_KEY     ROUTING_KEY(2, 19)

// use core 20 keys for alternate temperature distribution (fault tolerance)
#define ALT_TEMP_KEY       ROUTING_KEY(0, 20)
#define ALT_TEMP_NORTH_KEY ROUTING_KEY(16, 20)
#define ALT_TEMP_EAST_KEY  ROUTING_KEY(17, 20)
#define ALT_TEMP_SOUTH_KEY ROUTING_KEY(18, 20)
#define ALT_TEMP_WEST_KEY  ROUTING_KEY(19, 20)

#define CORE_MASK      0x0001fffe

#define NCh   (1 << NORTH)
#define SCh   (1 << SOUTH)
#define ECh   (1 << EAST)
#define WCh   (1 << WEST)
#define NECh ((1 << NORTH) | (1 << EAST))
#define NWCh ((1 << NORTH) | (1 << WEST))
#define SECh ((1 << SOUTH) | (1 << EAST))
#define SWCh ((1 << SOUTH) | (1 << WEST))

#define CHIP_ADDR(x, y)      ((x << 8) | y)

// ------------------------------------------------------------------------
// types
// ------------------------------------------------------------------------
typedef struct point
{
  uint          my_core;
  int           my_temp;
  uint          my_key;
  volatile int  neigh_temp[2][4];
  uint          neigh_key[4];
  volatile uint arrived[2];
  uint          init_arrived;
  volatile uint now;
  volatile uint next;
} point_t;


typedef struct point_list
{
  point_t           *mp;
  struct point_list *next;
} point_list_t;



// ------------------------------------------------------------------------
// variables
// ------------------------------------------------------------------------
uint coreID;
uint chipID;
uint my_chip, my_x, my_y;
uint loc_chip, loc_x, loc_y;

point_t      mp;
point_list_t pl;

/* multicast routing keys to communicate with neighbours */
//!!uint my_key;
//!!uint north_key;
//!!uint south_key;
//!!uint east_key;
//!!uint west_key;

uint rtr_conf;

uint dump_cnt = 0;
uint dump_msk;

/* temperature values */
//!!int my_temp = 0;  // any initial value will do!
//!!int old_temp = 0;  // any initial value will do!

// get temperatures from 4 neighbours
// make sure to have room for two values from each neighbour
// given that the communication is asynchronous
//!!volatile int neighbours_temp[2][4];

/* coeficients to compute new temperature value */
/* adjust for 16.16 fixed-point representation  */
int cx_adj = (int) (PARAM_CX * (1 << 16));
int cy_adj = (int) (PARAM_CY * (1 << 16));

/* keep track of which neighbours have sent data */
/* cores in the boder need special values! */
//!!volatile uint arrived[2];
//!!uint init_arrived;
//!!volatile uint now  = 0;
//!!volatile uint next = 1;

volatile uchar updating = TRUE;

sdp_msg_t my_msg;

/* report results in shared memory */
#ifndef OLD_SARK
static volatile int *core_temp;
#else
#ifdef USE_SDRAM
  static volatile int * const core_temp =
                     (int *) (SPINN_SDRAM_BASE + 0x1000 + 16 * sizeof(uint));
#else  //SYSRAM
  static volatile int * const core_temp =
                     (int *) (SPINN_SYSRAM_BASE + (SPINN_SYSRAM_SIZE / 2));
#endif
#endif

#ifdef DEBUG
  uint   dbg_packs_recv = 0;
  uint * dbg_keys_recv;
  uint   dbg_timeouts = 0;
  uint * dbg_stime;
#endif



void point_init (point_t *p, uint core)
{
  // prepare for first update
  p->my_core = core;
  p->my_key  = ROUTING_KEY(chipID, core);
  p->my_temp = 0;

  p->now  = 0;
  p->next = 1;

  p->init_arrived     = NONE_ARRIVED;

  // compute my neighbours' routing keys
  // cores on the borders don't receive data from all neighbours
  // instead use fixed border temperatures
  if (IS_NORTHERNMOST_CORE(core))
  {
    if (IS_NORTHERNMOST_CHIP(my_x, my_y))
    {
      // don't send packets north
      p->neigh_key[NORTH] = DONT_ROUTE_KEY;
      // don't expect packets from north
      p->neigh_temp[0][NORTH] = NORTH_INIT;
      p->neigh_temp[1][NORTH] = NORTH_INIT;
      p->init_arrived |= NORTH_ARRIVED;
    }
    else
    {
      p->neigh_key[NORTH] = ROUTING_KEY(CHIP_TO_NORTH(chipID), SOUTHERNMOST_CORE(core));
    }
  }
  else
  {
    // expect packets from north
    p->neigh_key[NORTH] = ROUTING_KEY(chipID, CORE_TO_NORTH(core));
  }

  if (IS_SOUTHERNMOST_CORE(core))
  {
    if (IS_SOUTHERNMOST_CHIP(my_x, my_y))
    {
      // don't send packets south
      p->neigh_key[SOUTH] = DONT_ROUTE_KEY;
      // don't expect packets from south
      p->neigh_temp[0][SOUTH] = SOUTH_INIT;
      p->neigh_temp[1][SOUTH] = SOUTH_INIT;
      p->init_arrived |= SOUTH_ARRIVED;
    }
    else
    {
      p->neigh_key[SOUTH] = ROUTING_KEY(CHIP_TO_SOUTH(chipID), NORTHERNMOST_CORE(core));
    }
  }
  else
  {
    // expect packets from south
    p->neigh_key[SOUTH] = ROUTING_KEY(chipID, CORE_TO_SOUTH(core));
  }

  if (IS_EASTERNMOST_CORE(core))
  {
    if (IS_EASTERNMOST_CHIP(my_x, my_y))
    {
      // don't send packets east
      p->neigh_key[EAST] = DONT_ROUTE_KEY;
      // don't expect packets from east
      p->neigh_temp[0][EAST] = EAST_INIT;
      p->neigh_temp[1][EAST] = EAST_INIT;
      p->init_arrived |= EAST_ARRIVED;
    }
    else
    {
      p->neigh_key[EAST] = ROUTING_KEY(CHIP_TO_EAST(chipID), WESTERNMOST_CORE(core));
    }
  }
  else
  {
    // expect packets from east
    p->neigh_key[EAST] = ROUTING_KEY(chipID, CORE_TO_EAST(core));
  }

  if (IS_WESTERNMOST_CORE(core))
  {
    if (IS_WESTERNMOST_CHIP(my_x, my_y))
    {
      // don't send packets west
      p->neigh_key[WEST] = DONT_ROUTE_KEY;
      // don't expect packets from west
      p->neigh_temp[0][WEST] = WEST_INIT;
      p->neigh_temp[1][WEST] = WEST_INIT;
      p->init_arrived |= WEST_ARRIVED;
    }
    else
    {
      p->neigh_key[WEST] = ROUTING_KEY(CHIP_TO_WEST(chipID), EASTERNMOST_CORE(core));
    }
  }
  else
  {
    // expect packets from west
    p->neigh_key[WEST] = ROUTING_KEY(chipID, CORE_TO_WEST(core));
  }

  p->arrived[0] = p->init_arrived;
  p->arrived[1] = p->init_arrived;
}


void routing_table_init ()
{
  uint my_route = 0;  // where I send my temperature

  uint route_from_north = FALSE;
  uint route_from_south = FALSE;
  uint route_from_east  = FALSE;
  uint route_from_west  = FALSE;

  if (IS_NORTHERNMOST_CORE(coreID))
  {
    if (!IS_NORTHERNMOST_CHIP(my_x, my_y))
    {
      // send packets to chip to the north
      my_route |= ROUTE_TO_LINK(NORTH_LINK);
      // expect packets from chip to the north (southernmost core)
      route_from_north = TRUE;
    }
  }
  else
  {
    // send to north core
    my_route |= ROUTE_TO_CORE(CORE_TO_NORTH(coreID));
  }

  if (IS_SOUTHERNMOST_CORE(coreID))
  {
    if (!IS_SOUTHERNMOST_CHIP(my_x, my_y))
    {
      // send packets to chip to the south
      my_route |= ROUTE_TO_LINK(SOUTH_LINK);
      // expect packets from chip to the south (northernmost core)
      route_from_south = TRUE;
    }
  }
  else
  {
    // send to south core
    my_route |= ROUTE_TO_CORE(CORE_TO_SOUTH(coreID));
  }

  if (IS_EASTERNMOST_CORE(coreID))
  {
    if (!IS_EASTERNMOST_CHIP(my_x, my_y))
    {
      // send packets to chip to the east
      my_route |= ROUTE_TO_LINK(EAST_LINK);
      // expect packets from chip to the east (westernmost core)
      route_from_east = TRUE;
    }
  }
  else
  {
    // send to east core
    my_route |= ROUTE_TO_CORE(CORE_TO_EAST(coreID));
  }

  if (IS_WESTERNMOST_CORE(coreID))
  {
    if (!IS_WESTERNMOST_CHIP(my_x, my_y))
    {
      // send packets to chip to the west
      my_route |= ROUTE_TO_LINK(WEST_LINK);
      // expect packets from chip to the west (easternmost core)
      route_from_west = TRUE;
    }
  }
  else
  {
    // send to west core
    my_route |= ROUTE_TO_CORE(CORE_TO_WEST(coreID));
  }
  /* ------------------------------------------------------------------- */

  /* ------------------------------------------------------------------- */
  /* initialise routing entries                                          */
  /* ------------------------------------------------------------------- */
  // allocate router entries
  uint e = rtr_alloc (5);
  if (e == 0)
    rt_error (RTE_ABORT);

  // set MC routing entry to send packets to my neighbours
  rtr_mc_set (e, 			// entry
	      pl.mp->my_key,             	// key
	      0xffffffff,         	// mask
	      my_route            	// route
	      );

  // set MC routing table entries to get packets from neighbour chips
  // north
  if (route_from_north)
  {
    rtr_mc_set (e + 1,     		// entry
		pl.mp->neigh_key[NORTH],            	// key
		0xffffffff,           	// mask
		ROUTE_TO_CORE(coreID) 	// route
		);
  }

  // south
  if (route_from_south)
  {
    rtr_mc_set (e + 2,     		// entry
		pl.mp->neigh_key[SOUTH],            	// key
		0xffffffff,           	// mask
		ROUTE_TO_CORE(coreID) 	// route
		);
  }

  // east
  if (route_from_east)
  {
    rtr_mc_set (e + 3,     		// entry
		pl.mp->neigh_key[EAST],             	// key
		0xffffffff,           	// mask
		ROUTE_TO_CORE(coreID) 	// route
		);
  }

  // west
  if (route_from_west)
  {
    rtr_mc_set (e + 4,     		// entry
		pl.mp->neigh_key[WEST],             	// key
		0xffffffff,           	// mask
		ROUTE_TO_CORE(coreID) 	// route
		);
  }
  /* ------------------------------------------------------------------- */

  /* ------------------------------------------------------------------- */
  /* initialise routing entries for host data and commands               */
  /* ------------------------------------------------------------------- */
  // only one core does it (to avoid duplication)
  if (leadAp)
  {
    uint e = rtr_alloc (4);
    if (e == 0)
      rt_error (RTE_ABORT);

    // setup the local (on-chip) routes
    uint loc_route = CORE_MASK;

    // TODO: needs fixing -- fault-tolerant tree
    // setup off-chip routes -- check for borders!
    uint off_route = 0;
    uint alt_route = 0;

    // north (only on y axis)
    if ((my_x == 0) && (my_y < (NUMBER_OF_YCHIPS - 1)))
    {
      off_route |= ROUTE_TO_LINK(NORTH_LINK);
    }

    // east (only on x axis)
    if ((my_x < (NUMBER_OF_XCHIPS - 1)) && (my_y == 0))
    {
      off_route |= ROUTE_TO_LINK(EAST_LINK);
    }

    // north-east (everywhere)
    if ((my_x < (NUMBER_OF_XCHIPS - 1)) && (my_y < (NUMBER_OF_YCHIPS - 1)))
    {
      off_route |= ROUTE_TO_LINK(NORTH_EAST_LINK);
    }

    // alternate south
    if ((my_x == 0) && (my_y != 1))
    {
      alt_route |= ROUTE_TO_LINK(SOUTH_LINK);
    }

    // alternate west
    if ((my_x != 1 ) && (my_y == 0))
    {
      alt_route |= ROUTE_TO_LINK(WEST_LINK);
    }

    // alternate south-west
    if ((my_x != 1) && (my_y != 1))
    {
      alt_route |= ROUTE_TO_LINK(SOUTH_WEST_LINK);
    }

    // command entry (matches any command)
    rtr_mc_set (e,                           	// entry
		CMD_KEY,                        // key
		CMD_MASK,                       // mask
		((loc_route << 6) | off_route)  // route
		);

    // alternate command entry (matches any command)
    rtr_mc_set (e + 1,                        	// entry
		ALT_CMD_KEY,                    // key
		CMD_MASK,                       // mask
		((loc_route << 6) | alt_route)  // route
		);

    // temperature entry (matches any temperature)
    if (IS_BORDER_CHIP(my_x, my_y))
    {
      // if border chip distribute temperatures locally
      rtr_mc_set (e + 2,                           // entry
                   TEMP_KEY,                       // key
                   TEMP_MASK,                      // mask
                   ((loc_route << 6) | off_route)  // route
                 );
      rtr_mc_set (e + 3,                           // entry
                   ALT_TEMP_KEY,                   // key
                   TEMP_MASK,                      // mask
                   ((loc_route << 6) | alt_route)  // route
                 );
    }
    else
    {
      // if not border chip pass temperatures on
      rtr_mc_set (e + 2,        // entry
                   TEMP_KEY,    // key
                   TEMP_MASK,   // mask
                   off_route    // route
                 );
      rtr_mc_set (e + 3,          // entry
                   ALT_TEMP_KEY,  // key
                   TEMP_MASK,     // mask
                   alt_route      // route
                 );
    }
  }
}
/*
*******/


void sieve_rtr_entries (uint droute, uint null)
{
  // compute the virtual broken cores from the received physical cores
  uint phys_mask = droute >> 6;
  uint virt_mask = 0;
  for (uint i = 0; i < NUM_CPUS; i++)
    if (phys_mask & (1 << i))
      virt_mask |= 1 << sv->p2v_map[i];

  // go through all router entries and strip broken cores
  rtr_entry_t e;
  uint dmask = virt_mask << 6;
  for (uint i = 0; i < MC_TABLE_SIZE; i++)
    if (rtr_mc_get (i, &e))
      if (e.route & dmask)
        rtr_mc_set (i, e.key, e.mask, (e.route & ~dmask));
}


void modify_rtr_entries (uint droute, uint null)
{
  // compute the virtual broken cores from the received physical cores
  // and add the corresponding points to my point list
  uint phys_mask = droute >> 6;
  uint virt_mask = 0;

  for (uint i = 0; i < NUM_CPUS; i++)
  {
    if (phys_mask & (1 << i))
    {
      uint vc = sv->p2v_map[i];
      virt_mask |= 1 << vc;

      // allocate memory for new point
      point_list_t *l = (point_list_t *) sark_alloc (1, sizeof (point_list_t));
      if (l == NULL)
        rt_error (RTE_ABORT);

      point_t *p = (point_t *) sark_alloc (1, sizeof (point_t));
      if (p == NULL)
        rt_error (RTE_ABORT);

      // initialise new point data
      point_init (p, vc);
      p->my_temp = core_temp[vc - 1];
      l->mp   = p;
      l->next = NULL;

      // and add it to the tail of the list
      point_list_t *t = &pl;

      while (t->next != NULL)
      {
        t = t->next;
      }
      t->next = l;
    }
  }

  // go through all router entries, strip broken cores and add me!
  rtr_entry_t e;
  uint dmask = virt_mask << 6;
  for (uint i = 0; i < MC_TABLE_SIZE; i++)
    if (rtr_mc_get (i, &e))
      if (e.route & dmask)
        rtr_mc_set (i, e.key, e.mask, ((e.route & ~dmask) | ROUTE_TO_CORE(coreID)));
}


INT_HANDLER dump_int_han (void)
{
  sark.vcpu->user2++;

  // get dumped packet type,
  uint type = rtr[RTR_DHDR] & RTR_TYPE_MASK;

  // get unresponsive cores and clear interrupt,
  uint droute = rtr[RTR_DSTAT] & dump_msk;

  // act only on multicast packets
  if ((type == PKT_TYPE_MC) && (droute != 0))
  {
    dump_cnt++;
    if ((dump_cnt) >= RTR_DUMP_CNT)
    {
      // strip broken cores from routing entries,
//!!      spin1_schedule_callback (sieve_rtr_entries, droute, 0, 1);
      spin1_schedule_callback (modify_rtr_entries, droute & ~ROUTE_TO_CORE(coreID), 0, 1);

      // adjust mask,
      dump_msk &= ~droute;

      // and restart counter
      dump_cnt = 0;
    }
  }
}


void router_init ()
{
  rtr_conf = rtr[RTR_CONTROL];  // save for later

  // configure router to use emergency routing
//!!lap  rtr[RTR_CONTROL] = (rtr_conf & 0x0000ffff) | 0x31310000;
}


void ijtag_init ()
{
  // reset the jtag signals
  sc[GPIO_CLR] = JTAG_TDI + JTAG_TCK + JTAG_TMS + JTAG_NTRST;

  // select internal jtag signals
  sc[SC_MISC_CTRL] |= JTAG_INT;
}


void dump_init (uint null0, uint null1)
{
  // point fiq vector to dump interrupt handler,
  sark_vec->fiq_vec = dump_int_han;

  // configure dump interrupt as fiq,
  vic[VIC_SELECT] = 1 << RTR_DUMP_INT;

  // enable dump interrupt,
  vic[VIC_ENABLE] = 1 << RTR_DUMP_INT;

  // clear router dump status and interrupt,
  (void) rtr[RTR_DSTAT];

  // and enable dump interrupt in the router
  rtr[RTR_CONTROL] |= (1 << RTR_DENABLE_BIT);

  // setup dump mask: leave links, monitor and myself out!
  dump_msk = RTR_DROUTE_MASK & ~ROUTE_TO_CORE(sv->v2p_map[0])
               & ~ROUTE_TO_CORE(sv->v2p_map[coreID]);
}


/****f* heat_demo.c/send_temps_to_host
*
* SUMMARY
*  This function is called at application exit.
*  It's used to report the final temperatures to the host
*
* SYNOPSIS
*  void send_temps_to_host ()
*
* SOURCE
*/
void send_temps_to_host ()
{
  // copy temperatures into msg buffer and set message length
  uint len = 16 * sizeof(uint);
  spin1_memcpy (my_msg.data, (void *) core_temp, len);
  my_msg.length = sizeof (sdp_hdr_t) + sizeof (cmd_hdr_t) + len;

  // and send SDP message!
  (void) spin1_send_sdp_msg (&my_msg, 100); // 100ms timeout
}
/*
*******/


void app_init ()
{
  // initialise point list
  pl.mp   = &mp;
  pl.next = NULL;

  // initialise user variables
  sark.vcpu->user0 = 0;
  sark.vcpu->user1 = 0;
  sark.vcpu->user2 = 0;

  #ifdef DEBUG
    // initialise variables
    dbg_keys_recv = spin1_malloc (DEBUG_KEYS * 4 * sizeof(uint));
    // record start time somewhere in SDRAM
    dbg_stime = (uint *) (SPINN_SDRAM_BASE + 4 * coreID);
    *dbg_stime = sv->clock_ms;
  #endif
}


/****f* heat_demo.c/sdp_init
*
* SUMMARY
*  This function is used to initialise SDP message buffer
*
* SYNOPSIS
*  void sdp_init ()
*
* SOURCE
*/
void sdp_init ()
{
  // fill in SDP destination fields
  my_msg.tag = 1;                    // IPTag 1
  my_msg.dest_port = PORT_ETH;       // Ethernet
  my_msg.dest_addr = sv->eth_addr;   // Ethernet-connected chip
//!  my_msg.dest_addr = 0;   // Root chip

  // fill in SDP source & flag fields
  my_msg.flags = 0x07;
  my_msg.srce_port = coreID;
  my_msg.srce_addr = sv->p2p_addr;
}
/*
*******/


/****f* heat_demo.c/report_temp
*
* SUMMARY
*  This function is used to report current temp
*
* SYNOPSIS
*  void report_temp (uint ticks)
*
* SOURCE
*/
void report_temp (uint ticks)
{
//!!  point_list_t *p = &pl;

//!!  while (p != NULL)
//!!  {
    // report temperature in shared memory
//!!    core_temp[(p->mp)->my_core - 1] = (p->mp)->my_temp;
//!!    p = p->next;
//!!  }

  // send results to host
  // only the lead application core does this
  if (leadAp)
  {
    // spread out the reporting to avoid SDP packet drop
//!    if ((ticks % (NUMBER_OF_XCHIPS * NUMBER_OF_YCHIPS)) == my_chip)
    if ((ticks % (BOARD_XCHIPS * BOARD_YCHIPS)) == loc_chip)
    {
      send_temps_to_host();
    }
  }
}
/*
*******/


/****f* heat_demo.c/report_results
*
* SUMMARY
*  This function is called at application exit.
*  It's used to report some statistics and say goodbye.
*
* SYNOPSIS
*  void report_results ()
*
* SOURCE
*/
void report_results ()
{
  /* report temperature in shared memory */
  core_temp[coreID - 1] = pl.mp->my_temp;

  /* report final temperature */
//  /* skew io_printfs to avoid congesting tubotron */
//  spin1_delay_us (200 * ((chipID << 5) + coreID));

  io_printf (IO_BUF, "T = %7.3f\n", pl.mp->my_temp);
}
/*
*******/


/****f* heat_demo.c/receive_data
*
* SUMMARY
*  This function is used as a callback for packet received events.
* receives data from 4 (NSEW) neighbours and updates the checklist
*
* SYNOPSIS
*  void receive_data (uint key, uint payload)
*
* INPUTS
*   uint key: packet routing key - provided by the RTS
*   uint payload: packet payload - provided by the RTS
*
* SOURCE
*/
void receive_data (uint key, uint payload)
{
  sark.vcpu->user1++;

  #ifdef DEBUG
    dbg_keys_recv[dbg_packs_recv++] = key;
    if (dbg_packs_recv == DEBUG_KEYS)
    {
      dbg_packs_recv = 0;
    }
  #endif

  if ((key & KEY_CORE_MASK) <= 16)
  {
    point_list_t *p = &pl;

    while (p != NULL)
    {
      if (key == (p->mp)->neigh_key[NORTH])
      {
        if ((p->mp)->arrived[(p->mp)->now] & NORTH_ARRIVED)
        {
          (p->mp)->neigh_temp[(p->mp)->next][NORTH] = payload;
          (p->mp)->arrived[(p->mp)->next] |= NORTH_ARRIVED;
        }
        else
        {
          (p->mp)->neigh_temp[(p->mp)->now][NORTH] = payload;
          (p->mp)->arrived[(p->mp)->now] |= NORTH_ARRIVED;
        }
      }
      else if (key == (p->mp)->neigh_key[SOUTH])
      {
        if ((p->mp)->arrived[(p->mp)->now] & SOUTH_ARRIVED)
        {
          (p->mp)->neigh_temp[(p->mp)->next][SOUTH] = payload;
          (p->mp)->arrived[(p->mp)->next] |= SOUTH_ARRIVED;
        }
        else
        {
          (p->mp)->neigh_temp[(p->mp)->now][SOUTH] = payload;
          (p->mp)->arrived[(p->mp)->now] |= SOUTH_ARRIVED;
        }
      }
      else if (key == (p->mp)->neigh_key[EAST])
      {
        if ((p->mp)->arrived[(p->mp)->now] & EAST_ARRIVED)
        {
          (p->mp)->neigh_temp[(p->mp)->next][EAST] = payload;
          (p->mp)->arrived[(p->mp)->next] |= EAST_ARRIVED;
        }
        else
        {
          (p->mp)->neigh_temp[(p->mp)->now][EAST] = payload;
          (p->mp)->arrived[(p->mp)->now] |= EAST_ARRIVED;
        }
      }
      else if (key == (p->mp)->neigh_key[WEST])
      {
        if ((p->mp)->arrived[(p->mp)->now] & WEST_ARRIVED)
        {
          (p->mp)->neigh_temp[(p->mp)->next][WEST] = payload;
          (p->mp)->arrived[(p->mp)->next] |= WEST_ARRIVED;
        }
        else
        {
          (p->mp)->neigh_temp[(p->mp)->now][WEST] = payload;
          (p->mp)->arrived[(p->mp)->now] |= WEST_ARRIVED;
        }
      }
      else
      {
        // unexpected packet!
        #ifdef DEBUG
          io_printf (IO_STD, "!\n");
        #endif
      }

      p = p->next;
    }
  }
  else
  {
    point_list_t *p = &pl;

    while (p != NULL)
    {
      if ((key == TEMP_NORTH_KEY) || (key == ALT_TEMP_NORTH_KEY))
      {
        if ((IS_NORTHERNMOST_CHIP(my_x, my_y)) &&
            (IS_NORTHERNMOST_CORE(coreID))
           )
        {
          (p->mp)->neigh_temp[(p->mp)->now][NORTH]  = payload;
          (p->mp)->neigh_temp[(p->mp)->next][NORTH] = payload;
        }
      }
      else if ((key == TEMP_EAST_KEY) || (key == ALT_TEMP_EAST_KEY))
      {
        if ((IS_EASTERNMOST_CHIP(my_x, my_y)) &&
            (IS_EASTERNMOST_CORE(coreID))
           )
        {
          (p->mp)->neigh_temp[(p->mp)->now][EAST]  = payload;
          (p->mp)->neigh_temp[(p->mp)->next][EAST] = payload;
        }
      }
      else if ((key == TEMP_SOUTH_KEY) || (key == ALT_TEMP_SOUTH_KEY))
      {
        if ((IS_SOUTHERNMOST_CHIP(my_x, my_y)) &&
            (IS_SOUTHERNMOST_CORE(coreID))
           )
        {
          (p->mp)->neigh_temp[(p->mp)->now][SOUTH]  = payload;
          (p->mp)->neigh_temp[(p->mp)->next][SOUTH] = payload;
        }
      }
      else if ((key == TEMP_WEST_KEY) || (key == ALT_TEMP_WEST_KEY))
      {
        if ((IS_WESTERNMOST_CHIP(my_x, my_y)) &&
            (IS_WESTERNMOST_CORE(coreID))
           )
        {
          (p->mp)->neigh_temp[(p->mp)->now][WEST]  = payload;
          (p->mp)->neigh_temp[(p->mp)->next][WEST] = payload;
        }
      }
      else if ((key == STOP_KEY) || (key == ALT_STOP_KEY))
      {
        spin1_exit (0);
      }
      else if ((key == PAUSE_KEY) || (key == ALT_PAUSE_KEY))
      {
        updating = FALSE;
      }
      else if ((key == RESUME_KEY)  | (key == ALT_RESUME_KEY))
      {
        updating = TRUE;
      }
      else
      {
        // unexpected packet!
        #ifdef DEBUG
          io_printf (IO_STD, "!\n");
        #endif
      }

      p = p->next;
    }
  }
}
/*
*******/


/****f* heat_demo.c/send_first_value
*
* SUMMARY
*
* SYNOPSIS
*  void send_first_value (uint a, uint b)
*
* SOURCE
*/
void send_first_value (uint a, uint b)
{
    /* send data to neighbours */
    spin1_send_mc_packet(pl.mp->my_key, pl.mp->my_temp, WITH_PAYLOAD);
}
/*
*******/


/****f* heat_demo.c/update
*
* SUMMARY
*
* SYNOPSIS
*  void update (uint ticks, uint b)
*
* SOURCE
*/
void update (uint ticks, uint b)
{
  sark.vcpu->user0++;

  if (updating)
  {
    point_list_t *p = &pl;

    while (p != NULL)
    {
      /* report if not all neighbours' data arrived */
      #ifdef DEBUG
        if ((p->mp)->arrived[(p->mp)->now] != ALL_ARRIVED)
        {
          io_printf (IO_STD, "@\n");
          dbg_timeouts++;
        }
      #endif
    
      // if a core does not receive temperature from a neighbour
      // it uses it's own as an estimate for the nieghbour's.
      if ((p->mp)->arrived[(p->mp)->now] != ALL_ARRIVED)
      {
        if (!((p->mp)->arrived[(p->mp)->now] & NORTH_ARRIVED))
        {
          (p->mp)->neigh_temp[(p->mp)->now][NORTH] = (p->mp)->my_temp;
        }
    
        if (!((p->mp)->arrived[(p->mp)->now] & SOUTH_ARRIVED))
        {
          (p->mp)->neigh_temp[(p->mp)->now][SOUTH] = (p->mp)->my_temp;
        }
    
        if (!((p->mp)->arrived[(p->mp)->now] & EAST_ARRIVED))
        {
          (p->mp)->neigh_temp[(p->mp)->now][EAST] = (p->mp)->my_temp;
        }
    
        if (!((p->mp)->arrived[(p->mp)->now] & WEST_ARRIVED))
        {
          (p->mp)->neigh_temp[(p->mp)->now][WEST] = (p->mp)->my_temp;
        }
      }
    
      /* compute new temperature */
      /* adjust for 16.16 fixed-point representation  */
      int tmp1 = (p->mp)->neigh_temp[(p->mp)->now][EAST] + (p->mp)->neigh_temp[(p->mp)->now][WEST]
                 - 2 * (p->mp)->my_temp;
      int tmp2 = (p->mp)->neigh_temp[(p->mp)->now][NORTH] + (p->mp)->neigh_temp[(p->mp)->now][SOUTH]
                 - 2 * (p->mp)->my_temp;
      /* adjust for 16.16 fixed-point representation  */
      int tmp3 = (int) (((long long) cx_adj * (long long) tmp1) >> 16);
      int tmp4 = (int) (((long long) cy_adj * (long long) tmp2) >> 16);
      (p->mp)->my_temp = (p->mp)->my_temp + tmp3 + tmp4;
    
      #ifdef POSITIVE_TEMP
        // avoids a problem with negative temps in the visualiser!
        (p->mp)->my_temp = ((p->mp)->my_temp > 0) ? (p->mp)->my_temp : 0;
      #endif
    
      /* send new data to neighbours */
      spin1_send_mc_packet((p->mp)->my_key, (p->mp)->my_temp, WITH_PAYLOAD);
    
      /* prepare for next iteration */
      (p->mp)->arrived[(p->mp)->now] = (p->mp)->init_arrived;
      (p->mp)->now  = 1 - (p->mp)->now;
      (p->mp)->next = 1 - (p->mp)->next;

      // report current
      core_temp[(p->mp)->my_core - 1] = (p->mp)->my_temp;
      p = p->next;
    }

    report_temp (ticks);
  }
}
/*
*******/


/****f* heat_demo.c/host_data
*
* SUMMARY
*
* SYNOPSIS
*  void host_data (uint *mailbox, uint port)
*
* INPUTS
*   uint mailbox: mailbox where the message is stored
*   uint port: destination port of the SDP message
*
* SOURCE
*/
void host_data (uint mailbox, uint port)
{
  sdp_msg_t *msg = (sdp_msg_t *) mailbox;
  uint *data = (uint *) msg->data;

  #ifdef DEBUG
    io_printf (IO_STD, "cmd: %d\n", msg->cmd_rc);
    if (msg->cmd_rc == 1)
    {
      io_printf (IO_STD, "N: %7.3f\n", data[0]);
      io_printf (IO_STD, "E: %7.3f\n", data[1]);
      io_printf (IO_STD, "S: %7.3f\n", data[2]);
      io_printf (IO_STD, "W: %7.3f\n", data[3]);
    }
  #endif

  switch (msg->cmd_rc)
  {
    case 0: // stop
      spin1_send_mc_packet(STOP_KEY, 0, NO_PAYLOAD);
      #if SEND_ALTERNATE == TRUE
        spin1_send_mc_packet(ALT_STOP_KEY, 0, NO_PAYLOAD);
      #endif
      break;

    case 1: // new border temperatures
      spin1_send_mc_packet(TEMP_NORTH_KEY, data[0], WITH_PAYLOAD);
      spin1_send_mc_packet(TEMP_EAST_KEY,  data[1], WITH_PAYLOAD);
      spin1_send_mc_packet(TEMP_SOUTH_KEY, data[2], WITH_PAYLOAD);
      spin1_send_mc_packet(TEMP_WEST_KEY,  data[3], WITH_PAYLOAD);
      #if SEND_ALTERNATE == TRUE
        spin1_send_mc_packet(ALT_TEMP_NORTH_KEY, data[0], WITH_PAYLOAD);
        spin1_send_mc_packet(ALT_TEMP_EAST_KEY,  data[1], WITH_PAYLOAD);
        spin1_send_mc_packet(ALT_TEMP_SOUTH_KEY, data[2], WITH_PAYLOAD);
        spin1_send_mc_packet(ALT_TEMP_WEST_KEY,  data[3], WITH_PAYLOAD);
      #endif
      break;

    case 2: // pause
      spin1_send_mc_packet(PAUSE_KEY, 0, NO_PAYLOAD);
      #if SEND_ALTERNATE == TRUE
        spin1_send_mc_packet(ALT_PAUSE_KEY, 0, NO_PAYLOAD);
      #endif
      break;

    case 3: // resume
      spin1_send_mc_packet(RESUME_KEY, 0, NO_PAYLOAD);
      #if SEND_ALTERNATE == TRUE
        spin1_send_mc_packet(ALT_RESUME_KEY, 0, NO_PAYLOAD);
      #endif
    break;

    default:
      // unexpected packet!
      #ifdef DEBUG
        io_printf (IO_STD, "!SDP\n");
      #endif
      break;
  }

  spin1_msg_free (msg);
}
/*
*******/


/****f* heat_demo.c/c_main
*
* SUMMARY
*  This function is called at application start-up.
*  It is used to register event callbacks and begin the simulation.
*
* SYNOPSIS
*  int c_main()
*
* SOURCE
*/
void c_main()
{
  #ifdef VERBOSE
    // say hello
    io_printf (IO_BUF, "starting heat_demo\n");
  #endif

  // get this core's ID
  coreID = spin1_get_core_id();
  chipID = spin1_get_chip_id();

  // get this chip's coordinates
  my_x = chipID >> 8;
  my_y = chipID & 0xff;
  //!!my_chip = (my_x * NUMBER_OF_YCHIPS) + my_y;

  // get this chip's local coordinates (i.e., relative to 48-node board)
  loc_x = sv->board_addr >> 8;
  loc_y = sv->board_addr & 0xff;
  loc_chip = (loc_x * BOARD_YCHIPS) + loc_y;

  // operate only if in core map!
  if ((my_x < NUMBER_OF_XCHIPS) && (my_y < NUMBER_OF_YCHIPS))
  {
    // keep temperatures in shared memory (only one core reports for all)
    core_temp = (volatile int *) sv->sysram_base; //##

    // set timer tick value to 1ms (in microseconds)
    // slow down simulation to alow users to appreciate changes
    spin1_set_timer_tick (TIMER_TICK_PERIOD);

    // register callbacks
    spin1_callback_on (MCPL_PACKET_RECEIVED, receive_data, 0);
    spin1_callback_on (TIMER_TICK, update, 0);
    spin1_callback_on (SDP_PACKET_RX, host_data, 0);

    // initialise application stuff
    app_init ();

    // initialise my point data
    point_init (&mp, coreID);

    // initialise routing tables
    routing_table_init ();

    // leadAp core is solely responsible for a few things
    if (leadAp)
    {
      // initialise SDP message buffer (to report temperatures)
      sdp_init ();

      // initialise router
      router_init ();

      #ifdef JTAG_INIT
        // initialise jtag pins
        ijtag_init ();
      #endif

      #ifdef DUMP_CHK
        // initialise dumped packet handling
        // NOTE: has to be done after the API initialises the VIC!
        spin1_schedule_callback (dump_init, 0, 0, 1);
      #endif

      // initialise temperatures (in case of absent cores!)
      for (uint i = 1; i <= 16; i++)
      {
        core_temp[i - 1] = 0;
      }
    }

    // kick-start the update process
    spin1_schedule_callback (send_first_value, 0, 0, 2);

    // go
    spin1_start (SYNC_WAIT);

    // restore router configuration
    rtr[RTR_CONTROL] = rtr_conf;

    #ifdef VERBOSE
      // report results
      report_results ();
    #endif
  }

  #ifdef VERBOSE
    // say goodbye
    io_printf (IO_BUF, "stopping heat_demo\n");
  #endif
}
/*
*******/
