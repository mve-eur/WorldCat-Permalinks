# WorldCat-Permalinks
# The idea:
Based on a list of ISBNs, connect with the WorldCat Search API and retrieve the permalinks of every ISBN.

# Requirements
pip install requests pandas openpyxl tqdm python-dotenv

# How to use:
1. Copy env_example.txt and rename it as ".env".

2. Fill in the API credentials: WSKEY (OCLC calls this 'Client ID'), WSKEY_SECRET (OCLC calls this 'Secret'), and INSTITUTION_SYMBOL.

3. Open input.xlsx and paste the desired ISBNs into column A, starting from cell A2.

4. Save the file and close it.

5. Navigate with your mouse to the folder that contains both the script and input.xlsx. Right-click in the folder and select “Open in Terminal.”

6. Type or copy/paste:
   python retrieve_links.py
   Warning: You cannot have either excel file open while running the script. Doing so will give you an error code [Permission denied]

7. Wait until the script has finished running 🙂
   You will know the script is complete when you see the following message:
   
   Script finished! Result saved in: C:\Users\.....
   PS C:\Users\.....

8. Open output.xlsx. You will now see three additional columns: OCN, Status, and Link.
   The Status column can contain various values, including error messages or multiple LHRs.

   
