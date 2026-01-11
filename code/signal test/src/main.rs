use serde::{Deserialize, Serialize};
use std::io::{Write};
use std::net::TcpStream;

#[derive(Serialize, Deserialize, Debug)]
struct Message {
    id: String,
    message: String,
}

fn main() -> std::io::Result<()> {
    let mut stream = TcpStream::connect("127.0.0.1:12345")?;
    println!("Connected to server");

    let msg = Message { id: "3".into(), message: "split".into() };
    let bytes = serde_json::to_vec(&msg)?;
    let len = (bytes.len() as u32).to_be_bytes();

    // Send message
    stream.write_all(&len)?;
    stream.write_all(&bytes)?;
    println!("Sent JSON: {:?}", msg);

    Ok(())
}
