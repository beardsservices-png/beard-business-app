"""
Import comprehensive service categories from homewyse-inspired data.
Run: python data/import_categories.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'beard_business.db')

CATEGORIES = [
  {
    "name": "Carpentry",
    "description": "Interior and exterior carpentry work including trim, cabinets, and custom woodwork",
    "subcategories": [
      ("Trim Carpentry", "Installation of baseboards, crown molding, door casings, and window trim"),
      ("Cabinet Installation", "Installation and adjustment of kitchen and bathroom cabinets"),
      ("Door Installation", "Installation of interior and exterior doors, including framing adjustments"),
      ("Framing", "Structural framing for walls, ceilings, and minor structural modifications"),
      ("Shelving & Built-ins", "Installation of shelves, built-in storage, and custom wooden features"),
      ("Furniture Assembly", "Assembly of furniture and built-in units on site"),
    ]
  },
  {
    "name": "Drywall",
    "description": "Drywall installation, repair, mudding, taping, and finish work",
    "subcategories": [
      ("Drywall Installation", "Hanging and fastening drywall panels to studs and joists"),
      ("Drywall Repair", "Patching holes, cracks, and damaged drywall sections"),
      ("Mudding & Taping", "Joint compound application and finishing of drywall seams"),
      ("Texture Application", "Application of drywall texture for ceiling and wall finishes"),
    ]
  },
  {
    "name": "Painting",
    "description": "Interior and exterior painting of walls, trim, cabinets, and specialty surfaces",
    "subcategories": [
      ("Interior Wall Painting", "Painting interior walls, ceilings, and stairwells"),
      ("Exterior Painting", "Painting exterior walls, siding, and trim"),
      ("Cabinet Painting", "Painting and refinishing of kitchen and bathroom cabinets"),
      ("Trim & Finish Painting", "Painting baseboards, crown molding, doors, and trim work"),
      ("Deck Staining & Sealing", "Staining, varnishing, and weatherproofing of wood decks and fences"),
      ("Wallpapering & Removal", "Installation and removal of wallpaper"),
    ]
  },
  {
    "name": "Flooring",
    "description": "Installation and repair of various flooring types including wood, tile, laminate, and vinyl",
    "subcategories": [
      ("Hardwood Flooring", "Installation of solid or engineered hardwood floors"),
      ("Tile Flooring", "Installation of ceramic, porcelain, and stone tile floors"),
      ("Laminate Flooring", "Installation of laminate planks and floating floors"),
      ("Vinyl Flooring", "Installation of vinyl plank and sheet flooring"),
      ("Carpet Installation", "Installation and stretching of carpet flooring"),
      ("Floor Repair", "Repair and replacement of damaged flooring sections"),
    ]
  },
  {
    "name": "Plumbing",
    "description": "Installation, repair, and maintenance of plumbing systems and fixtures",
    "subcategories": [
      ("Faucet Installation", "Installation and replacement of kitchen and bathroom faucets"),
      ("Toilet Installation", "Installation and replacement of toilets"),
      ("Sink Installation", "Installation of bathroom and kitchen sinks"),
      ("Shower & Tub Work", "Installation of showerheads, fixtures, and tub surrounds"),
      ("Pipe Repair & Replacement", "Repair and replacement of water supply and drain lines"),
      ("Water Heater Service", "Installation and maintenance of water heaters"),
      ("Drain Cleaning", "Cleaning and unclogging of drain lines"),
    ]
  },
  {
    "name": "Electrical",
    "description": "Installation, repair, and upgrade of electrical systems and fixtures",
    "subcategories": [
      ("Light Fixture Installation", "Installation of ceiling lights, chandeliers, and wall sconces"),
      ("Outlet & Switch Installation", "Installation of outlets, switches, and dimmer controls"),
      ("Circuit Upgrade", "Addition of circuits and upgrade of electrical panels"),
      ("Ceiling Fan Installation", "Installation and wiring of ceiling fans"),
      ("Exhaust Fan Installation", "Installation of bathroom and kitchen exhaust fans"),
      ("Thermostat Installation", "Installation of thermostats and smart home controls"),
    ]
  },
  {
    "name": "HVAC",
    "description": "Heating, ventilation, and air conditioning system installation, maintenance, and repair",
    "subcategories": [
      ("Furnace Installation", "Installation of gas and electric furnaces"),
      ("Air Conditioning Installation", "Installation of central air conditioning systems"),
      ("Heat Pump Installation", "Installation of heat pump systems"),
      ("Ductwork Installation", "Installation and sealing of HVAC ductwork"),
      ("HVAC Maintenance", "Regular maintenance, filter replacement, and system tune-ups"),
      ("Mini-Split Installation", "Installation of ductless mini-split heating and cooling units"),
    ]
  },
  {
    "name": "Roofing",
    "description": "Roofing installation, repair, and maintenance including shingles and gutters",
    "subcategories": [
      ("Asphalt Shingle Roofing", "Installation and repair of asphalt shingle roofs"),
      ("Metal Roofing", "Installation of metal roofing panels and standing seam"),
      ("Roof Repair", "Patching and repair of leaks and damaged roofing"),
      ("Gutter Installation", "Installation of gutters and downspouts"),
      ("Gutter Cleaning & Repair", "Cleaning and repair of existing gutters and downspouts"),
      ("Flashing Repair", "Installation and repair of roof flashing around penetrations"),
    ]
  },
  {
    "name": "Insulation",
    "description": "Installation and upgrade of insulation for thermal and acoustic purposes",
    "subcategories": [
      ("Attic Insulation", "Installation and upgrade of attic insulation"),
      ("Wall Insulation", "Installation of insulation in walls and cavities"),
      ("Basement Insulation", "Installation of basement and crawlspace insulation"),
      ("Pipe Insulation", "Insulation of water pipes for freeze protection and efficiency"),
      ("Weather Stripping", "Installation of weatherstripping around doors and windows"),
      ("Caulking & Sealing", "Caulking and sealing gaps for air and moisture control"),
    ]
  },
  {
    "name": "Landscaping",
    "description": "Outdoor landscaping and yard work including lawn care and hardscaping",
    "subcategories": [
      ("Mulch & Bed Installation", "Preparation and installation of landscape beds with mulch"),
      ("Lawn Maintenance", "Mowing, edging, and general yard upkeep"),
      ("Tree & Shrub Trimming", "Pruning and trimming of trees and shrubs"),
      ("Sod Installation", "Installation of grass sod for new or restored lawns"),
      ("Gravel & Stone", "Installation and raking of gravel and landscape stone"),
      ("Garden Preparation", "Tilling, soil amendment, and preparation for planting"),
    ]
  },
  {
    "name": "Fencing",
    "description": "Installation and repair of residential fencing including wood, vinyl, and chain-link",
    "subcategories": [
      ("Wood Fence Installation", "Installation of wood privacy, picket, and rail fences"),
      ("Vinyl Fence Installation", "Installation of vinyl fence panels and posts"),
      ("Chain-Link Fence", "Installation of chain-link fencing and gates"),
      ("Fence Repair", "Repair of damaged fence sections and replacement of posts"),
      ("Gate Installation", "Installation of fence gates and hardware"),
      ("Fence Staining & Sealing", "Staining, sealing, and weatherproofing of wood fences"),
    ]
  },
  {
    "name": "Concrete & Masonry",
    "description": "Concrete and masonry work including driveways, patios, and stone work",
    "subcategories": [
      ("Driveway Work", "Pouring, repair, and finishing of concrete driveways"),
      ("Patio Installation", "Installation of concrete or paverstone patios"),
      ("Walkway & Path Work", "Installation of concrete walks and garden paths"),
      ("Brick & Stone Masonry", "Installation of brick, stone, and pavers"),
      ("Concrete Repair", "Patching and repair of cracked or damaged concrete"),
      ("Retaining Wall", "Construction of retaining walls using block, stone, or timber"),
    ]
  },
  {
    "name": "Windows & Doors",
    "description": "Installation and repair of windows and exterior doors",
    "subcategories": [
      ("Window Installation", "Installation of new and replacement windows"),
      ("Exterior Door Installation", "Installation of entry doors and patio doors"),
      ("Window & Door Repair", "Repair of frames, seals, and hardware"),
      ("Glass & Glazing", "Installation of shower doors, mirrors, and glass enclosures"),
      ("Window Treatment", "Installation of blinds, shades, and curtain rods"),
      ("Storm Door Installation", "Installation of storm and screen doors"),
    ]
  },
  {
    "name": "Cleaning & Hauling",
    "description": "General cleaning and removal services including pressure washing and debris hauling",
    "subcategories": [
      ("Pressure Washing", "Pressure washing of driveways, decks, siding, and exterior surfaces"),
      ("Gutter Cleaning", "Cleaning of gutters and downspouts"),
      ("Deck Cleaning & Sealing", "Cleaning, staining, and sealing of wood decks"),
      ("Debris Hauling", "Removal and hauling away of construction and yard debris"),
      ("Junk Removal", "Removal of unwanted items and general clutter"),
      ("Post-Job Cleanup", "Final site cleanup after completion of a project"),
    ]
  },
  {
    "name": "Countertops",
    "description": "Installation of kitchen and bathroom countertops in various materials",
    "subcategories": [
      ("Granite Countertops", "Installation of granite slabs and countertops"),
      ("Laminate Countertops", "Installation of laminate countertops"),
      ("Quartz Countertops", "Installation of engineered quartz countertops"),
      ("Tile Countertops", "Installation of tile countertop surfaces"),
    ]
  },
  {
    "name": "Siding",
    "description": "Installation and repair of exterior siding",
    "subcategories": [
      ("Vinyl Siding", "Installation of vinyl siding panels and trim"),
      ("Wood Siding", "Installation and repair of wood siding"),
      ("Fiber Cement Siding", "Installation of fiber cement board siding"),
      ("Siding Repair", "Repair and replacement of damaged siding sections"),
    ]
  },
  {
    "name": "Decks & Outdoor Structures",
    "description": "Building and repair of outdoor decks, pergolas, and covered structures",
    "subcategories": [
      ("Deck Construction", "Building new wood and composite decks"),
      ("Deck Repair & Restoration", "Repair, refinishing, and restoration of existing decks"),
      ("Pergola & Gazebo", "Installation of pergolas, gazebos, and shade structures"),
      ("Railing Installation", "Installation of deck railings and spindles"),
      ("Patio Cover Installation", "Installation of awnings and patio covers"),
    ]
  },
  {
    "name": "Tile & Stone Work",
    "description": "Installation of decorative and functional tile and stone surfaces",
    "subcategories": [
      ("Floor Tile Installation", "Installation of ceramic, porcelain, and stone floor tiles"),
      ("Wall Tile & Backsplash", "Installation of tile for backsplashes and wall surfaces"),
      ("Shower Tile Work", "Installation of tile walls and shower surrounds"),
      ("Grout & Caulking Work", "Application and sealing of grout between tiles"),
      ("Tile Repair", "Replacement of cracked or damaged tiles"),
    ]
  },
  {
    "name": "Appliances",
    "description": "Installation of major and minor household appliances",
    "subcategories": [
      ("Range & Cooktop Installation", "Installation of gas and electric ranges and cooktops"),
      ("Dishwasher Installation", "Installation of dishwashers with proper plumbing and electrical"),
      ("Washer & Dryer Installation", "Installation of washers and dryers with proper connections"),
      ("Garbage Disposal Installation", "Installation of under-sink garbage disposals"),
      ("Microwave Installation", "Installation of over-the-range and built-in microwaves"),
    ]
  },
  {
    "name": "Garage Services",
    "description": "Garage door installation, repair, and garage improvements",
    "subcategories": [
      ("Garage Door Installation", "Installation of new garage door panels and systems"),
      ("Garage Door Repair", "Repair of springs, openers, and garage door hardware"),
      ("Garage Door Opener", "Installation and replacement of garage door openers"),
      ("Garage Storage", "Installation of storage shelving and organization systems"),
    ]
  },
  {
    "name": "Bathroom Remodeling",
    "description": "Complete bathroom renovation including fixtures, tile, and layout changes",
    "subcategories": [
      ("Vanity Installation", "Installation of bathroom vanities and cabinets"),
      ("Shower/Tub Remodel", "Complete renovation of shower and tub areas"),
      ("Bathroom Tile & Flooring", "Installation of bathroom tile and flooring"),
      ("Bathroom Lighting & Ventilation", "Installation of bathroom lighting and exhaust fans"),
    ]
  },
  {
    "name": "Kitchen Remodeling",
    "description": "Complete kitchen renovation including cabinets, counters, and appliances",
    "subcategories": [
      ("Kitchen Cabinet Installation", "Installation of new kitchen cabinets"),
      ("Kitchen Countertop Installation", "Installation of new kitchen countertops"),
      ("Backsplash Installation", "Installation of tile or stone backsplashes"),
      ("Kitchen Sink & Faucet", "Installation of kitchen sinks and faucets"),
    ]
  },
  {
    "name": "Site Assessment",
    "description": "Initial site visit for free estimates, measurements, and project scoping",
    "subcategories": [
      ("Free Estimate Visit", "Site visit to measure, assess scope, and provide a free estimate"),
      ("Paid Consultation", "Paid advisory or design consultation for larger projects"),
    ]
  },
  {
    "name": "Project Services",
    "description": "Support services for material runs, project coordination, and misc. tasks",
    "subcategories": [
      ("Material Acquisition & Delivery", "Time and mileage for picking up or delivering project materials"),
      ("Debris Haul Off", "Loading and hauling away of job-site waste and debris"),
      ("Project Management", "Coordination, scheduling, and oversight of multi-day or complex jobs"),
      ("Misc. Labor", "General labor tasks that do not fall under another specific category"),
    ]
  },
]


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT id, name FROM service_categories')
    existing = {r['name']: r['id'] for r in c.fetchall()}

    inserted_parents = 0
    inserted_subs = 0

    for cat in CATEGORIES:
        name = cat['name']
        if name in existing:
            parent_id = existing[name]
        else:
            c.execute(
                'INSERT OR IGNORE INTO service_categories (name, description, is_labor, parent_id) VALUES (?, ?, 1, NULL)',
                (name, cat['description'])
            )
            parent_id = c.lastrowid
            existing[name] = parent_id
            inserted_parents += 1

        for sname, sdesc in cat.get('subcategories', []):
            if sname not in existing:
                c.execute(
                    'INSERT OR IGNORE INTO service_categories (name, description, is_labor, parent_id) VALUES (?, ?, 1, ?)',
                    (sname, sdesc, parent_id)
                )
                existing[sname] = c.lastrowid
                inserted_subs += 1

    conn.commit()
    c.execute('SELECT COUNT(*) FROM service_categories')
    total = c.fetchone()[0]
    conn.close()
    print("Inserted", inserted_parents, "parent categories,", inserted_subs, "subcategories")
    print("Total categories in DB:", total)


if __name__ == '__main__':
    run()
