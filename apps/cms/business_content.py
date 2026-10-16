"""Editable business copy grounded in the catalogue and enquiry service options.

Project guides are proposed scopes, never evidence of completed installations.
No customer identities, prices, certifications or performance claims are seeded.
"""


def page(kind, slug, title, intro, sections, cta='Request a site assessment', url='/site-survey/'):
    return dict(kind=kind, slug=slug, title=title, intro=intro,
                body='\n\n'.join(f'{heading}\n{text}' for heading, text in sections),
                cta_label=cta, cta_url=url, meta_title=title,
                meta_description=intro[:160], is_published=True)


PAGES = [
    page('solution', 'cctv-surveillance', 'CCTV and video surveillance',
         'Plan camera coverage, recording and authorised viewing around your entrances, working areas and site conditions.', [
             ('Where to start', 'List the areas you need to monitor and the purpose of each view: an entrance, a counter, a passage or a perimeter. Agree which neighbouring and private areas must stay outside the camera view.'),
             ('What the system includes', 'The catalogue includes IP and analog cameras, NVR and DVR recorders, camera kits and installation accessories. Camera, recorder, power and cabling choices must be checked together; products are not interchangeable simply because they are listed under CCTV.'),
             ('What to confirm on site', 'Review mounting positions, lighting, cable routes, power availability and the required recording period. Storage is sized against the selected camera settings and recording schedule. Remote viewing requires a suitable network and secure account configuration.'),
             ('Before you approve', 'Ask for an itemised scope covering equipment, storage, installation, network work and any exclusions. Confirm how recording and playback will be demonstrated at handover. Do not assume a fixed camera count or retention period before assessment.')]),
    page('solution', 'smart-home-control', 'Smart switches, lighting and home control',
         'Plan room-by-room control for lighting, curtains and selected appliances, with wiring and device compatibility checked first.', [
             ('Choose the daily tasks', 'Start with the actions you want to simplify: switching lights, operating curtains or grouping selected devices into a routine. Prioritise rooms and essential controls before selecting devices.'),
             ('Catalogue options', 'Relevant categories include smart switches and lighting, smart curtains and blinds, and climate and appliance control. Each proposed device needs a compatible electrical load, installation arrangement and control method.'),
             ('Check before ordering', 'Confirm the existing wiring, switch-box dimensions, available network coverage and any controller requirements. Ask which functions remain available locally and which require an app, cloud service or internet connection. Voice and scene support must be verified for the exact models.'),
             ('Handover requirements', 'Include manual operation, account ownership and daily-use instructions in the agreed scope. Electrical modifications and curtain hardware should be explicitly listed in the quotation rather than assumed.')]),
    page('solution', 'networking-and-wifi', 'Networking and Wi-Fi coverage',
         'Build a network plan for connected devices, camera systems and everyday internet use instead of choosing equipment by room count alone.', [
             ('Define the requirement', 'Share the floor layout, internet entry point, approximate device count and areas where the connection is unreliable. Separate a provider connection problem from an indoor coverage problem.'),
             ('Relevant equipment', 'The catalogue covers routers, access points, networking and PoE switches. Switch ports, power requirements and cabling must match the chosen cameras and access points.'),
             ('Site assessment', 'Review wall construction, cable routes, mounting locations and power. Identify where wired connections are appropriate and where wireless coverage is needed. Do not assume a single router will cover every property.'),
             ('Acceptance checks', 'Agree the locations and devices to be tested. Include network names, administrator account handover and the responsibility for provider equipment. Internet speed and coverage depend on the connection, environment and selected hardware.')]),
    page('solution', 'door-entry-and-access', 'Door entry and access control',
         'Compare smart locks, access-control equipment and video door phones against your door, entry process and authorised users.', [
             ('Start with the entrance', 'Identify the door material, lock arrangement, opening direction and who needs access. For shared premises, decide who can add users and how access will be removed.'),
             ('Catalogue options', 'Smart locks and access control address entry permissions; video door phones and smart doorbells support visitor communication. These functions may require separate equipment and should not be assumed to work together without a model-specific check.'),
             ('Confirm compatibility', 'Check door dimensions, power or battery requirements, cable routes and network availability. Discuss emergency access and the intended behaviour during a power, battery or network interruption using the selected product documentation.'),
             ('Define the handover', 'Include authorised-user setup, administrator ownership and operating instructions. Door modifications, additional locks and civil work must be agreed separately in the scope.')]),
    page('solution', 'alarms-and-sensors', 'Intrusion alarms and smart sensors',
         'Plan entry and activity alerts around the areas you need to protect and the people responsible for responding.', [
             ('Define the event', 'Identify the doors, windows or indoor areas to monitor and when the system should be armed. Account for ordinary staff movement, visitors and pets where relevant.'),
             ('Plan the components', 'The intrusion alarms and smart sensors category is the starting point. Verify the exact sensor, controller and notification compatibility before combining products.'),
             ('Agree alert handling', 'Clarify who receives an alert, whether an internet connection is needed and what happens during power or connectivity loss. An equipment alert is not a promise of monitoring, emergency response or prevention.'),
             ('Commissioning', 'Include placement checks, controlled trigger tests and arming instructions. Ask how batteries, sensor faults and changes to the property should be handled after installation.')]),
    page('service', 'site-assessment-and-planning', 'Site assessment and system planning',
         'Turn your property layout and priorities into a defined scope before deciding quantities, installation work and budget.', [
             ('What to share', 'Provide the property type, area and city, approximate size, project stage and main requirements. Floor plans and existing equipment details help the discussion when available.'),
             ('What to review', 'Discuss coverage, wiring routes, available power, network access and mounting or door constraints. For an upgrade, identify equipment that may be retained and items requiring a compatibility check.'),
             ('What happens next', 'Submit a preferred visit time through the site-survey form. The team confirms scheduling and any applicable assessment charges before a visit. The requested time is not an automatic appointment confirmation.'),
             ('Quotation boundary', 'Ask for an itemised proposal with products, installation work, exclusions and acceptance checks. Final pricing and availability are confirmed through the quotation process.')]),
    page('service', 'installation-and-commissioning', 'Installation and commissioning',
         'Define installation, configuration and functional checks as part of the quotation, with clear responsibilities at handover.', [
             ('Before work starts', 'Agree the approved equipment list, installation locations, access to the premises and working hours. Confirm who handles electrical, civil and internet-provider work where required.'),
             ('Installation scope', 'Depending on the agreed solution, the scope can include mounting, cable routing, termination and equipment configuration. Extra cable runs, repairs and changes to approved locations require a revised scope.'),
             ('Functional checks', 'For CCTV, agree checks for camera views, recording and playback. For networking, specify test areas. For automation and access equipment, agree the functions and users to demonstrate for the selected models.'),
             ('Handover', 'Confirm account ownership, operating instructions and the route for reporting issues. Warranty terms, service charges and included follow-up work should be stated in the approved quotation.')], cta='Discuss installation', url='/contact/'),
    page('service', 'maintenance-and-amc', 'Maintenance and AMC enquiries',
         'Request an assessment of your existing system and agree maintenance coverage, exclusions and visit arrangements in writing.', [
             ('Information needed', 'Share the equipment make and model, approximate installation age, location, observed faults and any existing service contract. Explain whether the issue affects one device or the whole system.'),
             ('Possible assessment scope', 'Depending on the system, checks may cover connections, visible damage, recording status, storage condition, power and network connectivity. The final checklist depends on equipment access and the agreed service scope.'),
             ('Agree contract terms', 'Confirm visit frequency, included labour, chargeable parts, equipment exclusions and the process for requesting service. Do not assume unlimited visits, replacement equipment or a guaranteed response time unless written into the contract.'),
             ('Next step', 'Send the fault details or request a survey for maintenance or upgrades. A service enquiry is assessed before availability, charges or an AMC are confirmed.')], cta='Request maintenance support', url='/contact/'),
    page('service', 'system-upgrades', 'Existing-system assessment and upgrades',
         'Review what can be retained before replacing cameras, recorders, network equipment or connected controls.', [
             ('Document the existing system', 'List model numbers, camera or device quantities, recorder details and the symptoms or limitations you want to address. Existing passwords should be shared only through an agreed private handover process.'),
             ('Compatibility first', 'Check the intended additions against the recorder, controller, network, power and wiring already installed. A matching connector or brand does not by itself establish compatibility.'),
             ('Plan changes', 'Agree any interruption to recording, connectivity or access. Discuss configuration backup and whether old recordings or device settings need to be retained before work begins.'),
             ('Proposal and acceptance', 'Separate retained equipment, new equipment and labour in the proposal. Agree the functions to verify after the change and identify existing faults outside the upgrade scope.')], cta='Discuss an upgrade', url='/contact/'),
    page('project_guide', 'home-security-and-control-plan', 'Home security and everyday control plan',
         'A planning guide for combining entrance monitoring, selected smart controls and network coverage in a home or apartment.', [
             ('Project status', 'This is a proposed project scope, not a completed installation or customer case study.'),
             ('Priorities', 'Start with the main entrance, access arrangements and the rooms where lighting or curtain control would be useful. For apartments, confirm building rules before planning work in shared areas.'),
             ('Proposed work packages', 'Assess camera positions and recording needs; review door-entry compatibility; check wiring for selected smart controls; and assess Wi-Fi where connected devices will be installed. Each package can be quoted separately.'),
             ('Decisions before quotation', 'Confirm privacy boundaries, equipment locations, cable routes, app or controller dependencies and the household members who need access. Quantities and specific models follow the assessment.'),
             ('Acceptance checklist', 'Agree entrance views and playback checks where CCTV is selected, manual and app control checks for automation, and account handover. No project cost, completion date or claimed customer result is attached to this guide.')]),
    page('project_guide', 'shop-cctv-and-network-plan', 'Shop CCTV and network planning',
         'A planning guide for entrance, counter and stock-area monitoring, with recording and network requirements considered together.', [
             ('Project status', 'This is a proposed project scope, not evidence of a completed retail installation.'),
             ('Coverage discussion', 'Identify the entrance, checkout area, aisles and stock access points that matter to the business. Review views for obstructions and avoid unnecessarily recording neighbouring properties or private areas.'),
             ('System planning', 'Select camera and recorder types together, define the desired recording period and assess storage. Review power, cable routes and network access before promising remote viewing.'),
             ('Working around trading hours', 'Agree access, safe routing of cables and any downtime. Include the responsibility for provider connectivity, civil work and additional electrical points in the quotation.'),
             ('Acceptance checklist', 'Review agreed camera views, recording, playback and authorised access with the owner. Document any uncovered areas and exclusions. Device quantities and prices require an actual site assessment.')]),
    page('project_guide', 'office-access-and-connectivity-plan', 'Office access and connectivity plan',
         'A planning guide for staff connectivity, visitor entry and selected CCTV coverage across an office.', [
             ('Project status', 'This is a proposed office scope, not a completed customer project or a performance claim.'),
             ('Requirements discussion', 'Identify work areas, meeting rooms, visitor routes and restricted entrances. Estimate connected devices and decide which staff roles manage the network and entry permissions.'),
             ('Proposed work packages', 'Assess wired points, access-point positions and switch requirements. Review door hardware for access control and agree any CCTV views separately. Equipment interoperability must be verified for the chosen models.'),
             ('Operational planning', 'Agree installation hours, permitted interruptions and responsibility for network configuration. Define how administrator access, staff changes and visitor access will be handled.'),
             ('Acceptance checklist', 'Test the agreed network locations, authorised entry methods and any specified recording functions. Handover should identify account owners and support contacts. Final equipment, charges and timings remain subject to an approved proposal.')]),
]
