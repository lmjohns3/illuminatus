import Dexie from "dexie"

const DB = new Dexie("illuminatus")

DB.version(1).stores({
  state: "++id",
})

export default DB
