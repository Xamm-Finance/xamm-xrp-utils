const { XummSdk } = require("xumm-sdk");
const { Server } = require("socket.io");
const http = require("http");
const express = require("express");
const cors = require("cors");
require("dotenv").config();

const app = express();
app.use(cors());

const server = http.createServer(app);
const PORT = process.env.PORT || 3000;

const io = new Server(server, { cors: { origin: "*" } });

const Sdk = new XummSdk(process.env.API_KEY, process.env.API_SECRET);

io.on("connection", (socket) => {
  console.log("New User Connected");
  socket.on("signIn", async (req) => {
    console.log(req);
    const signInSub = await Sdk.payload.createAndSubscribe(req, (event) => {
      console.log("New payload event:", event.data);

      if (event.data.signed === true) {
        return event.data;
      }

      if (event.data.signed === false) {
        socket.emit("signIn", { txSign: false });
        return false;
      }
    });
    let qrCode = signInSub.created.refs.qr_png;
    socket.emit("signIn", { qrCode });

    const resolveData = await signInSub.resolved;

    if (resolveData.signed === false) {
      socket.emit("signIn", { txSign: false });
    }

    if (resolveData.signed === true) {
      const result = await Sdk.payload.get(resolveData.payload_uuidv4);
      let user_token = result.application.issued_user_token;
      let account = result.response.account;
      let network = result.response.environment_nodetype;
      socket.emit("signIn", { txSign: true, user_token, account, network });
    }
  });

  socket.on("signTxn", async (req) => {
    const subscription = await Sdk.payload.createAndSubscribe(req, (event) => {
      console.log("New payload event:", event.data);

      if (event.data.signed === true) {
        return event.data;
      }

      if (event.data.signed === false) {
        socket.emit("signTxn", { txSign: false });
        return false;
      }
    });

    let qrCode = subscription.created.refs.qr_png;
    console.log({ qrCode });
    socket.emit("signTxn", { qrCode });

    const resolveData = await subscription.resolved;

    if (resolveData.signed === false) {
      socket.emit("signTxn", { txSign: false });
    }

    if (resolveData.signed === true) {
      const result = await Sdk.payload.get(resolveData.payload_uuidv4);
      let account = result.response.account;
      let transactionId = result.response.txid;
      let network = result.response.environment_nodetype;
      socket.emit("signTxn", {
        txSign: true,
        account,
        transactionId,
        network,
      });
    }
  });
});

server.listen(PORT, () => console.log(`server running on port: ${PORT}`));
