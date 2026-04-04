import psycopg2

class DB:
    def __init__(self):
        self.conn = psycopg2.connect(
            database =  "workdatabase1",
            user = "postgres",
            password = "postgresql",
            host = "localhost",
            port = "5432"
        )

        self.curr = self.conn.cursor()
    
    def _commit(self):
        self.conn.commit()

    def _fetchall(self):
        return self.curr.fetchall()
    
    def _run(self , q):
        self.curr.execute(q)

    def close(self):
        self.curr.close()
        self.conn.close()   

    def select(self , q):
        self._run(q)
        r = self._fetchall()
        self.close()
        return r
    
    def insert(self, q):
        self._run(q)
        self._commit()
        self.close()
        return "ok inserted task"
    
class CreateLibrary:
    def run(self):
        print(DB().insert("""
             CREATE TABLE library(
             id INT PRIMARY KEY autoincrement, 
             name VARCHAR(50) , 
             books INT , 
             fine INT
             );
             """
        ))

class InsertDetails:
    def run(self):
        print(DB().insert("""
             INSERT INTO library ( name , books , fine)
             VALUES
             ('Ernest' , 5 , 0),
             ('Mark' , 2 , 10),
             ('Arthur' , 8 , 5),
             ('Brian' , 0 , 50),
             ('Chris' , 3 , 0);
             """
        ))

class SelectLetterStartsWithE:
    def run(self):
         print(DB().select("""
            SELECT id, name, books, fine
            FROM library
            WHERE name LIKE 'E%'
        """))


class SelectPatternR:
    def run(self):
        print(DB().select("""
            SELECT *
            FROM library
            WHERE name LIKE '__r%'
        """))

class SelectAll:
    def run(self):
        print(DB().select("SELECT * FROM library"))

if __name__ == "__main__":

    while True:
        print("----MENU----")
        print("1. Create Library Table")
        print("2. Insert Details")
        print("3. Select Names Starting with E")
        print("4. Select Names with 'r' as 3rd letter")
        print("5. Select All Records")
        print("6. Exit")
        choice = input("Enter your choice: ")
        if choice == '1':
            CreateLibrary().run()
        elif choice == '2':
            InsertDetails().run()
        elif choice == '3':
            SelectLetterStartsWithE().run()
        elif choice == '4':
            SelectPatternR().run()
        elif choice == '5':
            SelectAll().run()
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")
    