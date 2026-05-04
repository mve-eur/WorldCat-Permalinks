# WorldCat-Permalinks
# The idea:
Based on a list of ISBNs, connect with the WorldCat Search API and retrieve the permalinks of every ISBN.

# How to use:
1. Open input.xlsx and paste the desired ISBNs into column A, starting from cell A2.

2. Save the file and close it.

3. Navigate with your mouse to the folder that contains both the script and input.xlsx. Right-click in the folder and select “Open in Terminal.”

4. Type or copy/paste:
   python retrieve_links.py

5. Enter the password when prompted (this may take a moment).
   Note: The password is not visible while typing. If you enter an incorrect password, the script will stop. No worries—simply repeat step 4.

6. Wait until the script has finished running 🙂
   You will know the script is complete when you see the following message:
   
   Script finished! Result saved in: C:\Users\.....
   PS C:\Users\.....

7. Open output.xlsx. You will now see three additional columns: OCN, Status, and Link.
   The Status column can contain various values, including error messages or multiple LHRs.

   
