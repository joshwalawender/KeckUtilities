#!python3

## Import General Tools
import numpy as np
# transitions: https://github.com/pytransitions/transitions
from transitions import Machine


##-------------------------------------------------------------------------
## Site Info
##-------------------------------------------------------------------------
class GenericSite():
    def __init__(self, name, observers, used_before):
        '''
        '''
        self.name = name
        self.observers = observers
        self.used_before = used_before
        self.approved = None
        self.approval_email = 'unknown'

    def __str__(self):
        return f'{self.name}: {self.approved} for {self.observers}'

    def request_approval(self):
        '''
        '''
        print(f'Requesting approval from {self.name}')
        print(f'Sending email to {self.approval_email}')

    def notify_of_removal(self, request):
        '''
        '''
        print(f'Notifying site {self.name} that they have been removed from request')
        print(f'Sending email to {self.approval_email}')


class IfA(GenericSite):
    def __init__(self, observers, used_before):
        super().__init__('IfA', observers, used_before)
        self.approval_email = 'email@ifa.hawaii.edu'


class CIT(GenericSite):
    def __init__(self, observers, used_before):
        super().__init__('CIT', observers, used_before)
        self.approval_email = 'email@caltech.edu'


class UCB(GenericSite):
    def __init__(self, observers, used_before):
        super().__init__('UCB', observers, used_before)
        self.approval_email = 'email@berkeley.edu'


##-------------------------------------------------------------------------
## Request
##-------------------------------------------------------------------------
class Request():

    def __init__(self, progid, night, siteinfo, used_instrument):
        '''
        From the program ID, we can pull the telescope schedule and verify the
        list of nights and get the PI name and other metadata.
        
        progid: the program ID
        nights: an HST night from schedule on which this progid is observing
        siteinfo: a list of tuples:[(site, observers, used_site), (site, observers, used_site)]
                  where site is an approved site name, observers is a string of
                  observers names, and used_site is a Yes/No answer to the question
                  "Have one or more observers for this site used this site before?"
        used_instrument: a yes/no answer to the question "Have one or more
        members of the observing team used this instrument in the last 2 years?"

        For approvals, None is unapproved, False is denied, True is approved
        '''
        self.progid = progid
        self.allocating_institution = None # look up allocating institution
        self.night = night
        self.used_instrument = used_instrument
        self.sites = siteinfo
        self.keck_approved = None
        self.keck_approval_email = 'mainland_observing@keck.hawaii.edu'
        self.nasa_approved = None if self.allocating_institution == 'NASA' else True
        self.nasa_approval_email = 'email@nasa.gov'
        self.translator = {None: 'Pending', True: 'Approved', False: 'Denied'}

        # Make initial emails based on creation
        self.request_keck_approval()
        if self.nasa_approved is None:
            self.request_nasa_approval()
        for site in self.sites:
            if site.approved is None:
                site.request_approval()

        # Set up State Machine
        states = ['Requested', 'Approved', 'Denied', 'Cancelled']
        transitions = [
                       [ 'deny', ['Requested', 'Approved'], 'Denied' ],
                       [ 'cancel', '*', 'Cancelled' ],
                       [ 'all_approved', ['Requested', 'Denied'], 'Approved' ],
                       [ 'remove_approval', ['Requested', 'Approved'], 'Requested']
                      ]
        self.machine = Machine(model=self, states=states, transitions=transitions,
                          initial='Requested')


    def print_status(self):
        '''Prints approval status
        '''
        print(f"Approval Status:")
        print(f"    Keck: {self.translator[self.keck_approved]}")
        if self.allocating_institution == 'NASA':
            print(f"NASA: {self.translator[self.nasa_approved]}")
        for site in self.sites:
            print(f"{site.name:>8s}: {self.translator[site.approved]}")


    def check_status(self):
        '''Triggered after an action, checks whether the requests should change
        state.
        
        Check for denial
        
        '''
        # Check for any denials
        self._approvals = [site.approved for site in self.sites]
        self._approvals.append(self.keck_approved)
        self._approvals.append(self.nasa_approved)
        if np.all(self._approvals) == True:
            print('Remote observing request approved')
            self.all_approved()
        elif np.any([(x == False) for x in self._approvals]):
            print('Remote observing request denied')
            self.deny()
        elif self.state == 'Approved' and np.any([(x == None) for x in self._approvals]):
            print('Approval has been removed, resetting status to requested')
            self.remove_approval()
        else:
            self.print_status()
        print(f"State = {self.state}")
        print()

    def get_site(self, sitename):
        for i,site in enumerate(self.sites):
            if site.name.lower() == sitename.lower():
                return self.sites.pop(i)
        return None


    def request_keck_approval(self):
        print(f'Requesting approval from Keck')
        print(f'Sending email to {self.keck_approval_email}')


    def request_nasa_approval(self):
        print(f'Requesting approval from NASA')




    ## ------------------------------------------------------------------------
    ## Actions
    ## ------------------------------------------------------------------------
    def add_site(self, sitename, site_observers, site_used):
        print(f'Adding {sitename} with observers "{site_observers}"')
        for i,site in enumerate(self.sites):
            if site.name.lower() == sitename.lower():
                raise Exception(f"Site {sitename} already in request.")
        self.sites.append( SiteRequestInfo(name, observers, used_before) )
        self.check_status()

    def remove_site(self, site):
        print(f'Removing {sitename}')
        for i,site in enumerate(self.sites):
            if site.name.lower() == sitename.lower():
                removed = self.sites.pop(i)
        if removed.approved is True:
            removed.notify_of_removal(self)
        self.check_status()

    def approval(self, sitename, approved):
        print(f'Response from {sitename}: {self.translator[approved]}')
        if sitename.lower() == 'keck':
            self.keck_approved = approved
        elif sitename.lower() == 'nasa':
            self.nasa_approved = approved
        else:
            site = self.get_site(sitename)
            site.approved = approved
            self.sites.append(site)
        self.check_status()
    
    def site_info_edit(self, sitename, site_observers, site_used):
        pass



##-------------------------------------------------------------------------
## Statuses
##-------------------------------------------------------------------------
class Requested():
    def __init__(self):
        self.name = 'Requested'


class Approved():
    def __init__(self):
        self.name = 'Approved'


class Denied():
    def __init__(self):
        self.name = 'Denied'


class Cancelled():
    def __init__(self):
        self.name = 'Cancelled'


##-------------------------------------------------------------------------
## Main
##-------------------------------------------------------------------------
if __name__ == '__main__':
    r = Request('K123', '2020-07-20', [CIT('John Doe', True), IfA('Jane Doe', True)], True)
    print(f"State = {r.state}")
    print()
    r.approval('keck', True)
    r.approval('cit', True)
    r.approval('ifa', True)
    r.approval('ifa', None)
    r.approval('ifa', False)
    r.approval('ifa', True)
